"""
Genera usuarios y datos de prueba masivos (mapa / listados / app).

Correo: usuario{n}@loadtest.fixeo
Clave: password{n}

Por usuario crea: localización principal (LATAM), empresa (dueño), horarios 24h todos los días,
profesión + servicio, suscripción activa (plan Gratuito o el más barato) y trabajos.

Requisitos previos: seed_roles, seed_profesiones, seed_plans.

Uso:
  docker compose exec web python manage.py seed_loadtest_massive --count 1000 --jobs-per-user 4 --purge
"""

import random
import re
from datetime import time, timedelta
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.core.management.color import no_style
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from disponibilidad.models import Disponibilidad, Origen, Tipo
from empresas.models import Empresa, Horarios
from enums.enums import CURRENCY_CHOICES
from localizacion.models import Localizacion
from profesion.models import Profesion
from rol.models import Rol
from servicios.models import Servicio
from suscripciones.models import Plan, Subscripcion, SubscripcionSource, SubscripcionStatus
from trabajos.models import OfertaTrabajo, Trabajo
from usuario.models import Usuario
from usuario_localizacion.models import UsuarioLocalizacion
from usuario_profesion.models import UsuarioProfesion

# Empresa.esta_abierta compara dia_semana con timezone.localtime().strftime('%A').lower()
# (inglés en LC_TIME=C; en español son lunes, martes, …)
_HORARIO_DIAS = [
    'monday',
    'tuesday',
    'wednesday',
    'thursday',
    'friday',
    'saturday',
    'sunday',
    'lunes',
    'martes',
    'miércoles',
    'jueves',
    'viernes',
    'sábado',
    'domingo',
]
_HORA_APERTURA = time(0, 0, 0)
_HORA_CIERRE = time(23, 59, 59)

# Sufijo de correo para identificar y poder purgar sin tocar usuarios reales
EMAIL_SUFFIX = '@loadtest.fixeo'

# Centros urbanos LATAM + jitter (no puntos en el mar)
LA_SPOTS = [
    (-34.6037, -58.3816, 'Buenos Aires', 'CABA', 'Argentina', 'AMBA'),
    (-31.4201, -64.1888, 'Córdoba', 'Córdoba', 'Argentina', 'Capital'),
    (-32.8895, -68.8458, 'Mendoza', 'Mendoza', 'Argentina', 'Capital'),
    (-25.2637, -57.5759, 'Asunción', 'Central', 'Paraguay', 'Gran Asunción'),
    (-34.9011, -56.1645, 'Montevideo', 'Montevideo', 'Uruguay', 'Capital'),
    (-33.4489, -70.6693, 'Santiago', 'RM', 'Chile', 'Provincia'),
    (-12.0464, -77.0428, 'Lima', 'Lima', 'Perú', 'Provincia'),
    (-16.5000, -68.1500, 'La Paz', 'La Paz', 'Bolivia', 'Murillo'),
    (-17.7863, -63.1812, 'Santa Cruz', 'Santa Cruz', 'Bolivia', 'Andrés Ibáñez'),
    (-23.5505, -46.6333, 'São Paulo', 'SP', 'Brasil', 'Estadual'),
    (-22.9068, -43.1729, 'Río de Janeiro', 'RJ', 'Brasil', 'Estadual'),
    (-15.7939, -47.8828, 'Brasilia', 'DF', 'Brasil', 'Federal'),
    (-3.7319, -38.5267, 'Fortaleza', 'CE', 'Brasil', 'Estadual'),
    (-8.0476, -34.8770, 'Recife', 'PE', 'Brasil', 'Estadual'),
    (-19.9167, -43.9345, 'Belo Horizonte', 'MG', 'Brasil', 'Estadual'),
    (-30.0346, -51.2177, 'Porto Alegre', 'RS', 'Brasil', 'Estadual'),
    (4.7110, -74.0721, 'Bogotá', 'Cundinamarca', 'Colombia', 'Capital'),
    (6.2442, -75.5812, 'Medellín', 'Antioquia', 'Colombia', 'Aburrá'),
    (10.9639, -74.7964, 'Barranquilla', 'Atlántico', 'Colombia', 'Metropolitano'),
    (3.4516, -76.5320, 'Cali', 'Valle del Cauca', 'Colombia', 'Capital'),
    (11.0041, -74.8064, 'Cartagena', 'Bolívar', 'Colombia', 'Costa'),
    (10.4806, -66.9036, 'Caracas', 'Distrito Capital', 'Venezuela', 'Capital'),
    (8.2981, -62.7376, 'Ciudad Guayana', 'Bolívar', 'Venezuela', 'Caroní'),
    (-2.1894, -79.8891, 'Guayaquil', 'Guayas', 'Ecuador', 'Guayaquil'),
    (-0.1807, -78.4678, 'Quito', 'Pichincha', 'Ecuador', 'Distrito'),
    (9.9281, -84.0907, 'San José', 'San José', 'Costa Rica', 'Capital'),
    (14.6349, -90.5069, 'Ciudad de Guatemala', 'Guatemala', 'Guatemala', 'Capital'),
    (19.4326, -99.1332, 'Ciudad de México', 'CDMX', 'México', 'Capital'),
    (20.6597, -103.3496, 'Guadalajara', 'Jalisco', 'México', 'Estatal'),
    (25.6866, -100.3161, 'Monterrey', 'NL', 'México', 'Estatal'),
    (21.1619, -86.8515, 'Cancún', 'Quintana Roo', 'México', 'Benito Juárez'),
    (18.4655, -66.1057, 'San Juan', 'San Juan', 'Puerto Rico', 'Capital'),
    (18.4861, -69.9312, 'Santo Domingo', 'Distrito Nacional', 'Rep. Dominicana', 'Capital'),
    (23.1136, -82.3666, 'La Habana', 'La Habana', 'Cuba', 'Capital'),
    (-12.9714, -38.5014, 'Salvador', 'BA', 'Brasil', 'Estadual'),
    (-9.6658, -35.7353, 'Maceió', 'AL', 'Brasil', 'Estadual'),
    (-5.7945, -35.2110, 'Natal', 'RN', 'Brasil', 'Estadual'),
    (-1.4558, -48.5039, 'Belém', 'PA', 'Brasil', 'Estadual'),
    (-3.1190, -60.0217, 'Manaus', 'AM', 'Brasil', 'Estadual'),
]

TRABAJO_STATUSES = [s[0] for s in Trabajo.STATUS_CHOICES]
METODOS = [m[0] for m in Trabajo.PAYMENT_METHOD_CHOICES]
CURRENCIES = [c[0] for c in CURRENCY_CHOICES]

_USUARIO_INDEX_RE = re.compile(rf'^usuario(\d+){re.escape(EMAIL_SUFFIX)}$')


def _users_id_by_seed_index(count):
    """{ n: usuario_id } solo para correos usuario{n}@... esperados en este seed."""
    correos = [f'usuario{i}{EMAIL_SUFFIX}' for i in range(1, count + 1)]
    by_index = {}
    for u in Usuario.objects.filter(correo__in=correos).only('id', 'correo'):
        m = _USUARIO_INDEX_RE.match(u.correo)
        if m:
            by_index[int(m.group(1))] = u.id
    return by_index


def _reset_pk_sequences(*models):
    if connection.vendor != 'postgresql':
        return
    sql_list = connection.ops.sequence_reset_sql(no_style(), models)
    if not sql_list:
        return
    with connection.cursor() as cursor:
        for sql in sql_list:
            cursor.execute(sql)


def _random_lat_lon_city():
    spot = random.choice(LA_SPOTS)
    lat, lon = spot[0], spot[1]
    lat += random.uniform(-0.35, 0.35)
    lon += random.uniform(-0.35, 0.35)
    return lat, lon, spot[2], spot[3], spot[4], spot[5]


def _pais_code_from_country(country: str) -> str:
    """Código PAIS_CHOICES de Empresa a partir del nombre de país del seed LATAM."""
    extra = {
        'rep. dominicana': 'DO',
        'república dominicana': 'DO',
        'puerto rico': 'PR',
    }
    k = country.strip().lower()
    if k in extra:
        return extra[k]
    return Empresa.COUNTRY_NAME_TO_CODE.get(k, 'UY')


def _resolve_plan_gratuito():
    return (
        Plan.objects.filter(nombre__iexact='Gratuito', activo=True, is_deleted=False).first()
        or Plan.objects.filter(activo=True, is_deleted=False).order_by('precio').first()
    )


def _purge_loadtest_users(stdout, style):
    qs = Usuario.objects.filter(correo__endswith=EMAIL_SUFFIX)
    n = qs.count()
    if n == 0:
        stdout.write(style.WARNING('No hay usuarios loadtest para purgar.'))
        return
    uids = list(qs.values_list('id', flat=True))
    with transaction.atomic():
        Trabajo.objects.filter(profesional_id__in=uids).update(profesional_id=None)
        OfertaTrabajo.objects.filter(profesional_id__in=uids).delete()
        loc_ids = list(
            UsuarioLocalizacion.objects.filter(usuario_id__in=uids).values_list(
                'localizacion_id', flat=True
            )
        )
        Trabajo.objects.filter(localizacion_id__in=loc_ids).update(localizacion_id=None)
        Subscripcion.objects.filter(user_id__in=uids).delete()
        qs.delete()
        if loc_ids:
            Localizacion.objects.filter(id__in=loc_ids).delete()
    stdout.write(style.SUCCESS(f'Purgados {n} usuarios loadtest y localizaciones asociadas.'))


class Command(BaseCommand):
    help = (
        f'Crea usuarios masivos ({EMAIL_SUFFIX}): empresa, horarios 24h, ubicación principal, '
        'profesión/servicio, suscripción activa (plan Gratuito o el más barato) y trabajos. '
        'Pensado para mapa (is_owner_empresa + efectivo + sub). Usá --purge para reemplazar.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=1000,
            help='Cantidad de usuarios (default 1000)',
        )
        parser.add_argument(
            '--jobs-per-user',
            type=int,
            default=3,
            help='Trabajos por usuario (default 3)',
        )
        parser.add_argument(
            '--purge',
            action='store_true',
            help=f'Elimina usuarios con correo *{EMAIL_SUFFIX} y datos vinculados antes de crear.',
        )

    def handle(self, *args, **options):
        count = options['count']
        jobs_per_user = options['jobs_per_user']
        if count < 1:
            raise SystemExit('--count debe ser >= 1')
        if jobs_per_user < 0:
            raise SystemExit('--jobs-per-user debe ser >= 0')

        if options['purge']:
            _purge_loadtest_users(self.stdout, self.style)

        rol_usuario = Rol.objects.filter(nombre='usuario').first()
        if not rol_usuario:
            self.stderr.write(
                self.style.ERROR('No existe el rol "usuario". Ejecutá: python manage.py seed_roles')
            )
            raise SystemExit(1)

        rol_pro = Rol.objects.filter(nombre='profesional').first() or rol_usuario
        plan = _resolve_plan_gratuito()
        if not plan:
            self.stderr.write(
                self.style.ERROR('No hay planes activos (ej. Gratuito). Ejecutá: python manage.py seed_plans')
            )
            raise SystemExit(1)
        prof = Profesion.objects.filter(is_deleted=False).order_by('id').first()
        if not prof:
            self.stderr.write(
                self.style.ERROR('No hay profesiones. Ejecutá: python manage.py seed_profesiones')
            )
            raise SystemExit(1)

        now = timezone.now()
        users_batch = []
        for i in range(1, count + 1):
            correo = f'usuario{i}{EMAIL_SUFFIX}'
            users_batch.append(
                Usuario(
                    correo=correo,
                    password=make_password(f'password{i}'),
                    nombre='Usuario',
                    apellido=str(i),
                    telefono=f'+54911{str(i).zfill(7)}'[:20],
                    rol=rol_pro,
                    is_configured=True,
                    is_owner_empresa=True,
                    trabajo_domicilio=random.choice([True, False]),
                    trabajo_local=random.choice([True, False]),
                )
            )

        try:
            with transaction.atomic():
                Usuario.objects.bulk_create(users_batch, batch_size=500)
        except IntegrityError:
            self.stderr.write(
                self.style.ERROR(
                    f'No se pudieron crear usuarios (¿correos duplicados?). '
                    f'Ejecutá con --purge o borrá manualmente *{EMAIL_SUFFIX}.'
                )
            )
            raise SystemExit(1)

        by_index = _users_id_by_seed_index(count)
        if len(by_index) != count:
            self.stderr.write(
                self.style.WARNING(
                    f'Se crearon {len(by_index)}/{count} usuarios con el patrón usuarioN{EMAIL_SUFFIX}. '
                    'Si faltan, revisá duplicados o corrés con --purge.'
                )
            )
        if not by_index:
            self.stderr.write(self.style.ERROR('No hay usuarios para asociar ubicaciones/trabajos. Abortando.'))
            raise SystemExit(1)

        localizaciones = []
        ul_rows = []

        currencies = CURRENCIES
        for num, uid in sorted(by_index.items()):
            lat, lon, city, state, country, county = _random_lat_lon_city()
            loc = Localizacion(
                ubicacion=f'{city}, {country}',
                latitud=Decimal(str(round(lat, 7))),
                longitud=Decimal(str(round(lon, 7))),
                address=f'Calle demo {num}',
                city=city,
                country=country,
                county=county,
                state=state,
                isPrimary=True,
            )
            localizaciones.append((num, uid, loc))

        uids_for_pick = [uid for _, uid, _ in localizaciones]

        _reset_pk_sequences(Localizacion)
        with transaction.atomic():
            loc_objs = [t[2] for t in localizaciones]
            Localizacion.objects.bulk_create(loc_objs, batch_size=500)
            for (num, uid, loc), saved in zip(localizaciones, loc_objs):
                ul_rows.append(
                    UsuarioLocalizacion(
                        usuario_id=uid,
                        localizacion_id=saved.pk,
                        es_principal=True,
                    )
                )
            UsuarioLocalizacion.objects.bulk_create(ul_rows, batch_size=500)

        empresas = []
        usuario_profesiones = []
        servicios = []
        for num, uid, loc in localizaciones:
            empresas.append(
                Empresa(
                    nombre=f'Empresa loadtest #{num}',
                    ubicacion=loc.ubicacion,
                    descripcion=f'Empresa demo loadtest usuario {num}',
                    latitud=loc.latitud,
                    longitud=loc.longitud,
                    pais=_pais_code_from_country(loc.country),
                    admin_id=Usuario(pk=uid),
                    localizacion=loc,
                    unipersonal=True,
                    vende_servicios=True,
                    vende_productos=False,
                    acepta_efectivo=True,
                    acepta_tarjeta=False,
                    is_mercadopago_vinculado=False,
                    currency=random.choice(currencies),
                )
            )
            usuario_profesiones.append(
                UsuarioProfesion(usuario_id=uid, profesion_id=prof.id)
            )
            servicios.append(
                Servicio(
                    usuario_id=uid,
                    profesion_id=prof.id,
                    nombre='Servicio demo',
                    precio=Decimal('2500.00'),
                    divisa='ARS',
                    tiempo=60,
                )
            )

        _reset_pk_sequences(Empresa)
        with transaction.atomic():
            Empresa.objects.bulk_create(empresas, batch_size=500)

        horarios_rows = []
        for emp in empresas:
            for dia in _HORARIO_DIAS:
                horarios_rows.append(
                    Horarios(
                        empresa_id=emp.pk,
                        dia_semana=dia,
                        hora_inicio=_HORA_APERTURA,
                        hora_fin=_HORA_CIERRE,
                        enabled=True,
                    )
                )
        _reset_pk_sequences(Horarios)
        with transaction.atomic():
            Horarios.objects.bulk_create(horarios_rows, batch_size=1000)

        _reset_pk_sequences(UsuarioProfesion)
        with transaction.atomic():
            UsuarioProfesion.objects.bulk_create(usuario_profesiones, batch_size=500)

        _reset_pk_sequences(Servicio)
        with transaction.atomic():
            Servicio.objects.bulk_create(servicios, batch_size=500)

        trabajos = []
        for num, uid, loc in localizaciones:
            loc_id = loc.pk
            for j in range(jobs_per_user):
                delta_days = random.randint(-120, 90)
                start = now + timedelta(days=delta_days, hours=random.randint(0, 23))
                duration_h = random.randint(1, 6)
                end = start + timedelta(hours=duration_h)
                status = random.choice(TRABAJO_STATUSES)
                prof_id = None
                if status in ('aceptado', 'finalizado', 'cancelado'):
                    candidates = [x for x in uids_for_pick if x != uid]
                    if candidates:
                        prof_id = random.choice(candidates)

                trabajos.append(
                    Trabajo(
                        usuario_id=uid,
                        profesional_id=prof_id,
                        descripcion=(
                            f'Trabajo demo #{j + 1} usuario {num} — '
                            f'{random.choice(["plomería", "electricidad", "pintura", "limpieza", "jardinería"])} '
                            f'en {loc.ubicacion}'
                        ),
                        status=status,
                        esUrgente=random.random() < 0.08,
                        fecha_inicio=start,
                        fecha_fin=end if random.random() < 0.85 else None,
                        precio_final=Decimal(str(random.randint(5_000, 800_000))),
                        localizacion_id=loc_id,
                        metodo_pago=random.choice(METODOS),
                        currency=random.choice(currencies),
                    )
                )

        _reset_pk_sequences(Trabajo)
        with transaction.atomic():
            Trabajo.objects.bulk_create(trabajos, batch_size=500)

        expiracion_sub = now + timedelta(days=400)
        subscripciones = [
            Subscripcion(
                user_id=Usuario(pk=uid),
                plan_id=plan,
                expiracion=expiracion_sub,
                cancelada=False,
                jobs_restantes=plan.cantidad_jobs,
                source=SubscripcionSource.MANUAL,
                status=SubscripcionStatus.ACTIVE,
            )
            for num, uid, loc in localizaciones
        ]
        _reset_pk_sequences(Subscripcion)
        with transaction.atomic():
            Subscripcion.objects.bulk_create(subscripciones, batch_size=500)

        # Disponibilidad opcional alrededor de algunos trabajos (origen trabajo)
        disp = []
        for t in trabajos:
            if random.random() < 0.4:
                disp.append(
                    Disponibilidad(
                        usuario_id=t.usuario_id,
                        fecha_inicio=t.fecha_inicio or now,
                        fecha_fin=(t.fecha_fin or t.fecha_inicio or now) + timedelta(hours=2),
                        tipo=Tipo.DISPONIBLE,
                        origen=Origen.TRABAJO,
                    )
                )
        if disp:
            _reset_pk_sequences(Disponibilidad)
            with transaction.atomic():
                Disponibilidad.objects.bulk_create(disp, batch_size=500)

        self.stdout.write(
            self.style.SUCCESS(
                f'\nListo: hasta {len(by_index)} usuarios ({EMAIL_SUFFIX}), '
                f'rol profesional, empresa, horarios, ubicación principal, servicio, suscripción activa, '
                f'password password<1..N>, ~{jobs_per_user} trabajos c/u.\n'
                f'Ejemplo login: usuario1{EMAIL_SUFFIX} / password1'
            )
        )
