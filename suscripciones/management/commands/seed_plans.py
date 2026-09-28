from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from suscripciones.models import Plan, Subscripcion


PLANES_SEED = [
    {
        'nombre': 'Básica',
        'descripcion': 'Ideal para empezar a mostrar tu negocio en la app.',
        'precio': 6.99,
        'cantidad_personas': 1,
        'duracion': timedelta(days=30),
        'activo': True,
        'google_play_id': '',
        'appstore_id': '',
        'caracteristicas': [
            'Acceso al mapa de profesionales',
            'Soporte básico',
            'Estadísticas contables y cartera de clientes para tu negocio',
        ],
        'tiene_landing_page': False,
        'recomendado': False,
        'slogan': 'Básica',
        'color': '#929AA7',
        'badge_mapa_url': 'https://azfnkddnmhqczaydgver.supabase.co/storage/v1/object/public/ALaVueltaImagenes/pins/pin_basica.png',
        'user_badge_url': 'https://azfnkddnmhqczaydgver.supabase.co/storage/v1/object/public/ALaVueltaImagenes/pins/badge_rounded_basica.png',
    },
    {
        'nombre': 'Pro',
        'descripcion': 'Para negocios que quieren crecer con marketing y mejor posicionamiento.',
        'precio': 12.99,
        'cantidad_personas': 1,
        'duracion': timedelta(days=30),
        'activo': True,
        'google_play_id': '',
        'appstore_id': '',
        'caracteristicas': [
            'Acceso al mapa de profesionales',
            'Soporte pro',
            'Estadísticas contables y cartera de clientes para tu negocio, agregando marketing para cupones de descuentos',
            'Mejor posicionamiento que la Básica',
            'Landing page web',
        ],
        'tiene_landing_page': True,
        'recomendado': True,
        'slogan': 'Pro',
        'color': '#2B70CA',
        'badge_mapa_url': 'https://azfnkddnmhqczaydgver.supabase.co/storage/v1/object/public/ALaVueltaImagenes/pins/pin_pro.png',
        'user_badge_url': 'https://azfnkddnmhqczaydgver.supabase.co/storage/v1/object/public/ALaVueltaImagenes/pins/badge_rounded_pro.png',
    },
    {
        'nombre': 'Membresía Gold',
        'descripcion': 'El plan más completo: máxima visibilidad y asistencia con IA.',
        'precio': 14.99,
        'cantidad_personas': 1,
        'duracion': timedelta(days=30),
        'activo': True,
        'google_play_id': '',
        'appstore_id': '',
        'caracteristicas': [
            'Acceso al mapa de profesionales',
            'Soporte pro',
            'Estadísticas contables y cartera de clientes para tu negocio, agregando marketing para cupones de descuentos',
            'Mejor posicionamiento que la Básica y la Pro',
            'Landing page web',
            'Recomendación de asistente IA',
        ],
        'tiene_landing_page': True,
        'recomendado': False,
        'slogan': 'Gold',
        'color': '#CD981E',
        'badge_mapa_url': 'https://azfnkddnmhqczaydgver.supabase.co/storage/v1/object/public/ALaVueltaImagenes/pins/pin_gold.png',
        'user_badge_url': 'https://azfnkddnmhqczaydgver.supabase.co/storage/v1/object/public/ALaVueltaImagenes/pins/badge_rounded_gold.png',
    },
]

_STORE_FIELDS = ('google_play_id', 'appstore_id')
PLAN_BASICA_NOMBRE = 'Básica'


def _defaults_from_seed(plan_data):
    """Valores listos para create/update (sin nombre; precio como Decimal; IDs vacíos → None)."""
    out = {}
    for key, value in plan_data.items():
        if key == 'nombre':
            continue
        if key == 'precio':
            out[key] = Decimal(str(value))
        elif key in _STORE_FIELDS:
            out[key] = value or None
        else:
            out[key] = value
    return out


class Command(BaseCommand):
    help = (
        'Crea o actualiza los planes desde PLANES_SEED (precio, descripción, jobs, tiendas, etc.). '
        'La clave natural es nombre. Los planes que ya no están en PLANES_SEED se desactivan '
        '(activo=False, nunca se borran: Subscripcion.plan_id es CASCADE y perderíamos historial), '
        'y las suscripciones activas que apuntaban a un plan desactivado se migran a "Básica".'
    )

    def handle(self, *args, **kwargs):
        nombres_nuevos = {p['nombre'] for p in PLANES_SEED}
        planes_por_nombre = {}

        for plan_data in PLANES_SEED:
            defaults = _defaults_from_seed(plan_data)
            plan, created = Plan.objects.get_or_create(
                nombre=plan_data['nombre'],
                defaults=defaults,
            )
            planes_por_nombre[plan.nombre] = plan
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Plan "{plan.nombre}" creado')
                )
                continue

            changed_fields = []
            for field, new_value in defaults.items():
                current = getattr(plan, field)
                if current != new_value:
                    setattr(plan, field, new_value)
                    changed_fields.append(field)

            if changed_fields:
                plan.save()
                self.stdout.write(
                    self.style.WARNING(
                        f'~ Plan "{plan.nombre}" actualizado: {", ".join(changed_fields)}'
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'- Plan "{plan.nombre}" sin cambios')
                )

        # Desactiva (no borra) los planes que ya no forman parte del seed actual.
        planes_viejos = Plan.objects.exclude(nombre__in=nombres_nuevos).filter(activo=True)
        nombres_viejos = list(planes_viejos.values_list('nombre', flat=True))
        if nombres_viejos:
            planes_viejos.update(activo=False)
            self.stdout.write(
                self.style.WARNING(
                    f'~ Desactivados {len(nombres_viejos)} plan(es) viejo(s): {", ".join(nombres_viejos)}'
                )
            )

        # Migra a "Básica" las suscripciones ACTIVAS (no canceladas, no vencidas —
        # misma definición que suscripciones.utils.get_subscripcion_activa) que
        # apuntaban a un plan viejo ahora desactivado. Los usuarios sin
        # suscripción activa quedan tal cual (no se les asigna nada).
        plan_basica = planes_por_nombre.get(PLAN_BASICA_NOMBRE)
        if plan_basica and nombres_viejos:
            subs_a_migrar = Subscripcion.objects.filter(
                cancelada=False,
                expiracion__gt=timezone.now(),
                plan_id__nombre__in=nombres_viejos,
            )
            cantidad_subs = subs_a_migrar.count()
            if cantidad_subs:
                subs_a_migrar.update(plan_id=plan_basica)
                self.stdout.write(
                    self.style.WARNING(
                        f'~ Migradas {cantidad_subs} suscripción(es) activa(s) de planes viejos a "{PLAN_BASICA_NOMBRE}"'
                    )
                )

        self.stdout.write(
            self.style.SUCCESS('\n✅ Seed de planes completado')
        )
