"""Herramientas (function-calling) del agente de WhatsApp.

Cada tool consulta/escribe sobre los modelos reales de Fixeo. Reciben la
``ConversacionWhatsApp`` activa (para conocer ubicación y usuario) más los
argumentos que decide el modelo, y devuelven dicts serializables a JSON.
"""
import logging
from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from localizacion.utils import calcular_distancia_km
from . import geo

logger = logging.getLogger(__name__)

RADIO_DEFAULT_KM = 15.0
LIMITE_DEFAULT = 8

DIAS_ES = {1: 'lunes', 2: 'martes', 3: 'miércoles', 4: 'jueves', 5: 'viernes', 6: 'sábado', 7: 'domingo'}


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------
def _bbox(lat, lon, radio_km):
    """Bounding box aproximado para prefiltrar por lat/lon antes del haversine."""
    dlat = radio_km / 111.0
    dlon = radio_km / (111.0 * max(0.1, abs(_cos(lat))))
    return lat - dlat, lat + dlat, lon - dlon, lon + dlon


def _cos(lat):
    import math
    return math.cos(math.radians(float(lat)))


def _empresas_cercanas(conv, radio_km, extra_filter=None):
    from empresas.models import Empresa

    lat, lon = float(conv.ubicacion_lat), float(conv.ubicacion_lon)
    min_lat, max_lat, min_lon, max_lon = _bbox(lat, lon, radio_km)
    qs = Empresa.objects.filter(
        latitud__range=(min_lat, max_lat),
        longitud__range=(min_lon, max_lon),
    )
    if extra_filter is not None:
        qs = qs.filter(extra_filter)

    resultados = []
    for emp in qs[:200]:
        dist = calcular_distancia_km(lat, lon, emp.latitud, emp.longitud)
        if dist <= radio_km:
            resultados.append((dist, emp))
    resultados.sort(key=lambda x: x[0])
    return resultados


def _require_ubicacion(conv):
    if not conv.tiene_ubicacion:
        return {'necesita_ubicacion': True,
                'mensaje': 'Necesito saber la ubicación del usuario. Pedile que escriba su zona, ciudad o dirección en texto.'}
    return None


INVITADO_CORREO = 'invitado.whatsapp@fixeo.app'


def _usuario_invitado_whatsapp():
    """Cuenta compartida (placeholder) para pedidos/reservas de invitados sin cuenta."""
    from usuario.models import Usuario
    u = Usuario.objects.filter(correo=INVITADO_CORREO).first()
    if u:
        return u
    u = Usuario.objects.create(correo=INVITADO_CORREO, nombre='Invitado WhatsApp',
                               apellido='', telefono='', is_configured=False)
    u.set_unusable_password()
    u.save(update_fields=['password'])
    return u


def _resolver_cliente(conv):
    """Devuelve (usuario, telefono_invitado).

    Trae el usuario por teléfono (wa_id). Si NO existe, NO crea un usuario por
    pedido: usa la cuenta compartida 'Invitado WhatsApp' y devuelve el teléfono
    para guardarlo en el registro (phoneNumberInvitedUser + notas).
    """
    from usuario.models import Usuario
    tel = conv.wa_id or ''
    if conv.usuario_id and conv.usuario and conv.usuario.correo != INVITADO_CORREO:
        return conv.usuario, ''
    existente = Usuario.objects.filter(telefono__endswith=tel[-8:]).first() if tel else None
    if existente:
        conv.usuario = existente
        conv.save(update_fields=['usuario', 'ultima_actividad'])
        return existente, ''
    return _usuario_invitado_whatsapp(), tel


def _resolver_servicio(profesional_id, servicio_id, descripcion=None):
    """Devuelve un Servicio del profesional. Valida el id; si no corresponde,
    intenta matchear por nombre contra la descripción (el modelo alucina ids)."""
    from servicios.models import Servicio
    qs = Servicio.objects.filter(usuario_id=profesional_id)
    if servicio_id:
        s = qs.filter(id=servicio_id).first()
        if s:
            return s
    if descripcion:
        d = descripcion.strip().lower()
        if d:
            for s in qs:
                nom = (s.nombre or '').strip().lower()
                if nom and (nom in d or d in nom):
                    return s
    return None


def _localizacion_profesional(profesional):
    """Localización del profesional (su principal o la de su empresa)."""
    from localizacion.models import Localizacion
    ul = (profesional.localizaciones.filter(es_principal=True).select_related('localizacion').first()
          or profesional.localizaciones.select_related('localizacion').first())
    if ul and ul.localizacion_id:
        return ul.localizacion
    emp = profesional.empresas_administradas.first()
    if emp and emp.localizacion_id:
        return emp.localizacion
    if emp:
        return Localizacion.objects.create(
            ubicacion=emp.ubicacion or 'Local del profesional', address=emp.ubicacion or '',
            latitud=emp.latitud, longitud=emp.longitud,
            city=emp.ubicacion or '', county='', state='', country='Uruguay')
    return None


def _localizacion_domicilio(conv, direccion):
    """Crea una Localizacion para el domicilio del cliente a partir de la dirección dada."""
    from localizacion.models import Localizacion
    r = geo.geocode_texto(direccion, pais=conv.pais or 'UY')
    if r:
        lat, lon = r['lat'], r['lon']
    elif conv.tiene_ubicacion:
        lat, lon = float(conv.ubicacion_lat), float(conv.ubicacion_lon)
    else:
        return None
    return Localizacion.objects.create(
        ubicacion=direccion, address=direccion,
        latitud=Decimal(str(lat)), longitud=Decimal(str(lon)),
        city=conv.ciudad or '', county='', state='', country=conv.pais or 'Uruguay')


def _serial_empresa(emp, dist=None):
    data = {
        'empresa_id': emp.id,
        'nombre': emp.nombre,
        'descripcion': (emp.descripcion or '')[:200],
        'ubicacion': emp.ubicacion,
        'vende_productos': emp.vende_productos,
        'vende_servicios': emp.vende_servicios,
        'vende_menu_diario': emp.vende_menu_diario,
        'abierta_ahora': emp.esta_abierta(),
    }
    if dist is not None:
        data['distancia_km'] = dist
    return data


# ---------------------------------------------------------------------------
# Tools de ubicación
# ---------------------------------------------------------------------------
def set_ubicacion(conv, zona=None):
    resultado = geo.geocode_texto(zona, pais=conv.pais or 'UY')
    if not resultado:
        return {'ok': False, 'mensaje': f'No pude ubicar "{zona}". Pedile que escriba una zona/ciudad más simple (por ej. solo la ciudad).'}
    conv.ubicacion_lat = Decimal(str(resultado['lat']))
    conv.ubicacion_lon = Decimal(str(resultado['lon']))
    conv.ciudad = resultado.get('ciudad', '') or conv.ciudad
    conv.pais = resultado.get('pais', '') or conv.pais
    if conv.estado == conv.ESTADO_ESPERANDO_UBICACION:
        conv.estado = conv.ESTADO_IDLE
    conv.save(update_fields=['ubicacion_lat', 'ubicacion_lon', 'ciudad', 'pais', 'estado', 'ultima_actividad'])
    return {'ok': True, 'ubicacion': resultado.get('place_name') or conv.ciudad}


# ---------------------------------------------------------------------------
# Tools de lectura — negocios
# ---------------------------------------------------------------------------
def _serial_busqueda(f, flags=None):
    """Compacta una fila del servicio de búsqueda para el LLM (solo datos reales).

    `flags` es un dict {empresa_id: {vende_productos, vende_servicios, vende_menu_diario}}
    para que el modelo sepa cómo rutear (pedido vs turno).
    """
    es_prod = f.get('tipo') == 'producto'
    empresa_id = f.get('empresa_id')
    ef = (flags or {}).get(empresa_id) or {}
    vende_prod = ef.get('vende_productos')
    vende_serv = ef.get('vende_servicios')
    return {
        'tipo': f.get('tipo'),  # usuario (profesional/negocio) | servicio | producto
        # id del profesional/negocio dueño (sirve para reservar / ver disponibilidad / detalle)
        'profesional_id': None if es_prod else f.get('id'),
        'usuario_id': f.get('id'),
        'titulo': f.get('titulo'),
        'profesiones': f.get('extra') if f.get('tipo') == 'usuario' else None,
        'empresa': f.get('empresa_nombre') or f.get('business_name'),
        'empresa_id': empresa_id,
        'producto_id': f.get('producto_id'),
        'precio': str(f['precio']) if f.get('precio') is not None else (
            str(f['precio_servicio']) if f.get('precio_servicio') is not None else None),
        'rating': f.get('rating'),
        'distancia_km': f.get('distancia_km'),
        'ciudad': f.get('ciudad'),
        # Tipo de negocio → cómo se puede operar:
        'vende_productos': vende_prod,
        'vende_servicios': vende_serv,
        'vende_menu_diario': ef.get('vende_menu_diario'),
        'puede_reservar_turno': bool(vende_serv),   # sólo servicios toman turnos
        'puede_pedir_productos': bool(vende_prod),   # sólo productos aceptan pedidos
    }


def _flags_empresas(filas):
    """Batch: {empresa_id: flags} para las filas que tengan empresa."""
    ids = {f.get('empresa_id') for f in filas if f.get('empresa_id')}
    if not ids:
        return {}
    from empresas.models import Empresa
    return {
        e['id']: e
        for e in Empresa.objects.filter(id__in=ids).values(
            'id', 'vende_productos', 'vende_servicios', 'vende_menu_diario')
    }


def _resolver_profesion(texto):
    """Devuelve una Profesion si `texto` matchea (exacto/plural/contiene) el catálogo, si no None."""
    if not texto:
        return None
    from profesion.models import Profesion
    t = str(texto).strip()
    if len(t) < 3:
        return None
    candidatos = [t]
    low = t.lower()
    if low.endswith('es') and len(t) > 4:
        candidatos.append(t[:-2])
    if low.endswith('s') and len(t) > 3:
        candidatos.append(t[:-1])
    for c in candidatos:  # match exacto primero
        p = Profesion.objects.filter(nombre__iexact=c).first()
        if p:
            return p
    for c in candidatos:  # luego "contiene" (ej. "jardinero" -> "Jardinero")
        p = Profesion.objects.filter(nombre__icontains=c).first()
        if p:
            return p
    return None


def buscar(conv, termino=None, tipo=None, profesion=None, radio_km=None, limite=LIMITE_DEFAULT):
    """Búsqueda unificada (profesionales, negocios, servicios y productos) cercana.

    Si el pedido es por oficio (el `profesion` o el `termino` matchean una profesión
    del catálogo), filtra ESTRICTO por esa profesión — sin similaridad de texto, para
    no traer falsos positivos. Si no, cae a la búsqueda por similaridad (trigram).
    Siempre filtra por distancia a la ubicación del usuario y excluye su cuenta.
    """
    falta = _require_ubicacion(conv)
    if falta:
        return falta

    from usuario.search_service import buscar_unificado, recomendados_cercanos

    lat, lon = float(conv.ubicacion_lat), float(conv.ubicacion_lon)
    radio = float(radio_km) if radio_km else RADIO_DEFAULT_KM
    exclude_id = conv.usuario_id or 0
    limite = int(limite)
    termino = (termino or '').strip()
    pool = max(limite * 3, 20)

    # ¿Es una búsqueda por oficio? Resolvemos la profesión desde `profesion` o el `termino`.
    prof = _resolver_profesion(profesion)
    if prof is None and tipo not in ('productos', 'servicios'):
        prof = _resolver_profesion(termino)

    if prof is not None and tipo != 'productos':
        # Filtro ESTRICTO por profesión: profesionales de ese oficio cercanos (sin trigram).
        filas = recomendados_cercanos(
            tipo='profesional', exclude_id=exclude_id, profesion_id=prof.id,
            lat=lat, lng=lon, radio_km=radio, limit=pool, filtrar_elegibles=False,
        )
    elif termino:
        filas = buscar_unificado(
            termino, exclude_id=exclude_id, profesion_id=(prof.id if prof else None),
            lat=lat, lng=lon, radio_km=radio, limit=pool, filtrar_elegibles=False,
        )
    else:
        rec_tipo = 'producto' if tipo == 'productos' else ('servicio' if tipo == 'servicios' else 'profesional')
        filas = recomendados_cercanos(
            tipo=rec_tipo, exclude_id=exclude_id, profesion_id=(prof.id if prof else None),
            lat=lat, lng=lon, radio_km=radio, limit=pool, filtrar_elegibles=False,
        )

    if tipo == 'productos':
        filas = [f for f in filas if f.get('tipo') == 'producto']
    elif tipo in ('profesionales', 'negocios'):
        filas = [f for f in filas if f.get('tipo') == 'usuario']
    elif tipo == 'servicios':
        filas = [f for f in filas if f.get('tipo') in ('usuario', 'servicio')]

    filas = filas[:limite]
    flags = _flags_empresas(filas)
    items = [_serial_busqueda(f, flags) for f in filas]
    _recordar_profesionales(conv, items)
    return {'total': len(items), 'radio_km': radio, 'profesion_detectada': prof.nombre if prof else None,
            'resultados': items}


def _recordar_profesionales(conv, items):
    """Persiste en la conversación los profesionales de la última búsqueda.

    Sirve para validar/autocorregir el `profesional_id` que manda el modelo en
    reservas/disponibilidad (los LLM a veces alucinan un id que no vino de la tool).
    """
    cands = [{'id': it['profesional_id'], 'titulo': it.get('titulo'), 'empresa_id': it.get('empresa_id')}
             for it in items if it.get('profesional_id')]
    # También guardamos empresas (de profesionales y de productos) para resolver empresa_id.
    empresas, vistos = [], set()
    for it in items:
        eid = it.get('empresa_id')
        if eid and eid not in vistos:
            vistos.add(eid)
            empresas.append({'empresa_id': eid, 'titulo': it.get('empresa') or it.get('titulo')})
    try:
        slots = dict(conv.slots or {})
        slots['ultimos_profesionales'] = cands
        slots['ultimas_empresas'] = empresas
        conv.slots = slots
        conv.save(update_fields=['slots', 'ultima_actividad'])
    except Exception:  # pragma: no cover - no romper la búsqueda por esto
        logger.exception('No pude guardar ultimos_profesionales')


def _resolver_empresa_id(conv, eid):
    """Valida/autocorrige `empresa_id` contra la última búsqueda (mismo criterio que profesional)."""
    cands = (conv.slots or {}).get('ultimas_empresas') or []
    ids = [c.get('empresa_id') for c in cands if c.get('empresa_id')]
    try:
        eid = int(eid)
    except (TypeError, ValueError):
        eid = None
    if eid in ids:
        return eid, None
    if len(set(ids)) == 1:
        return ids[0], None
    if ids:
        return None, {'ok': False, 'id_invalido': True,
                      'mensaje': ('Ese empresa_id no está en la última búsqueda. Elegí uno de '
                                  'estos ids EXACTOS y volvé a llamar la herramienta.'),
                      'opciones': cands}
    return eid, None


def _resolver_profesional_id(conv, pid):
    """Valida/autocorrige `pid` contra la última búsqueda.

    Devuelve (id_valido, error_dict). Si el id no está en la última búsqueda:
    - si hubo un único profesional, usa ese (el modelo claramente se refería a él);
    - si hubo varios, devuelve un error pidiendo reelegir de la lista;
    - si no hay contexto de búsqueda previo, deja pasar el id tal cual.
    """
    cands = (conv.slots or {}).get('ultimos_profesionales') or []
    ids = [c.get('id') for c in cands if c.get('id')]
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        pid = None
    if pid in ids:
        return pid, None
    if len(ids) == 1:
        return ids[0], None
    if ids:
        return None, {'ok': False, 'id_invalido': True,
                      'mensaje': ('Ese profesional_id no está en la última búsqueda. Elegí uno de '
                                  'estos ids EXACTOS y volvé a llamar la herramienta.'),
                      'opciones': cands}
    return pid, None


def detalle_negocio(conv, empresa_id):
    from empresas.models import Empresa
    empresa_id, err = _resolver_empresa_id(conv, empresa_id)
    if err:
        return err
    emp = Empresa.objects.filter(id=empresa_id).first()
    if not emp:
        return {'ok': False, 'mensaje': 'No encontré ese negocio.'}
    horarios = [
        {'dia': h.dia_semana, 'inicio': str(h.hora_inicio), 'fin': str(h.hora_fin)}
        for h in emp.horarios.filter(enabled=True)
    ]
    data = _serial_empresa(emp)
    data.update({
        'acepta_efectivo': emp.acepta_efectivo,
        'acepta_tarjeta': emp.acepta_tarjeta,
        'horarios': horarios,
    })
    return data


def listar_productos(conv, empresa_id, buscar=None, limite=15):
    from empresas.models import Producto
    empresa_id, err = _resolver_empresa_id(conv, empresa_id)
    if err:
        return err
    qs = Producto.objects.filter(empresa_id=empresa_id, es_menu_diario=False, agotado=False)
    if buscar:
        qs = qs.filter(nombre__icontains=buscar)
    productos = [
        {'producto_id': p.id, 'nombre': p.nombre, 'precio': str(p.precio),
         'divisa': p.divisa, 'descripcion': (p.descripcion or '')[:120]}
        for p in qs[:int(limite)]
    ]
    return {'total': len(productos), 'productos': productos}


def menu_del_dia(conv, empresa_id, dia_semana=None):
    _eid, _err = _resolver_empresa_id(conv, empresa_id)
    if _err:
        return _err
    empresa_id = _eid
    from empresas.models import Producto
    dia = int(dia_semana) if dia_semana else timezone.localtime().isoweekday()
    qs = Producto.objects.filter(
        empresa_id=empresa_id, es_menu_diario=True, agotado=False,
        dias_menu__dia_semana=dia, dias_menu__activo=True,
    ).distinct()
    platos = [
        {'producto_id': p.id, 'nombre': p.nombre, 'precio': str(p.precio),
         'divisa': p.divisa, 'descripcion': (p.descripcion or '')[:120]}
        for p in qs[:30]
    ]
    return {'dia': DIAS_ES.get(dia, str(dia)), 'total': len(platos), 'platos': platos}


# ---------------------------------------------------------------------------
# Tools de lectura — profesionales
# ---------------------------------------------------------------------------
def listar_servicios_profesional(conv, profesional_id):
    from servicios.models import Servicio
    profesional_id, err = _resolver_profesional_id(conv, profesional_id)
    if err:
        return err
    servicios = [
        {'servicio_id': s.id, 'nombre': s.nombre, 'profesion': s.profesion.nombre,
         'precio': str(s.precio), 'divisa': s.divisa, 'tiempo_min': s.tiempo,
         'acepta_domicilio': s.acepta_domicilio}
        for s in Servicio.objects.select_related('profesion').filter(usuario_id=profesional_id)
    ]
    return {'total': len(servicios), 'servicios': servicios}


def disponibilidad_profesional(conv, profesional_id, fecha=None):
    """Disponibilidad real derivada del horario de la empresa menos lo ocupado.

    Semántica: si no hay bloques cargados para el día, está libre en todo el
    horario de su empresa. Con `fecha` (YYYY-MM-DD) devuelve las horas libres;
    sin fecha, los días disponibles del mes actual.
    """
    from usuario.models import Usuario
    from servicios.models import Servicio
    from empresas.models import Horarios
    from disponibilidad.utils import horas_disponibles, dias_disponibles

    print("recibo prof id", profesional_id)
    profesional_id, err = _resolver_profesional_id(conv, profesional_id)
    if err:
        return err

    prof = Usuario.objects.filter(id=profesional_id).first()
    if not prof:
        return {'ok': False, 'mensaje': 'No encontré a ese profesional.'}

    empresa = prof.empresas_administradas.first()
    print(empresa);
    if not empresa:
        return {'ok': True, 'sin_horarios': True,
                'mensaje': 'Este profesional no tiene negocio configurado; coordiná el día y hora directamente con él.'}

    # Solo los negocios que venden SERVICIOS toman turnos. Los de productos van por pedido.
    if not empresa.vende_servicios:
        return {'ok': True, 'toma_turnos': False, 'vende_productos': empresa.vende_productos,
                'empresa_id': empresa.id,
                'mensaje': ('Este negocio vende productos y NO toma turnos con calendario. '
                            'Si querés, podés hacer un pedido de sus productos.')}

    if not Horarios.objects.filter(empresa=empresa, enabled=True).exists():
        return {'ok': True, 'sin_horarios': True,
                'mensaje': 'Este profesional no tiene horarios cargados; coordiná el día y hora directamente con él.'}

    # Duración de referencia: el servicio más corto del profesional, o 60'.
    dur = (Servicio.objects.filter(usuario_id=profesional_id)
           .order_by('tiempo').values_list('tiempo', flat=True).first()) or 60

    if fecha:
        slots = horas_disponibles(prof, fecha, dur)
        libres = [s['hora'] for s in slots if s['disponible']]
        return {'ok': True, 'fecha': fecha, 'duracion_min': dur,
                'total': len(libres), 'horas_libres': libres}

    ahora = timezone.localtime()
    dias = dias_disponibles(prof, ahora.year, ahora.month, dur)
    return {'ok': True, 'anio': ahora.year, 'mes': ahora.month, 'duracion_min': dur,
            'dias_disponibles': dias}


# ---------------------------------------------------------------------------
# Tools de escritura — reserva (Trabajo)
# ---------------------------------------------------------------------------
def crear_reserva(conv, profesional_id, fecha_inicio, descripcion=None, servicio_id=None,
                  es_domicilio=False, direccion=None, metodo_pago=None):
    from usuario.models import Usuario
    from servicios.models import Servicio
    from trabajos.models import Trabajo, TrabajoServicio

    profesional_id, err = _resolver_profesional_id(conv, profesional_id)
    if err:
        return err

    profesional = Usuario.objects.filter(id=profesional_id).first()
    if not profesional:
        return {'ok': False, 'mensaje': 'No encontré a ese profesional.'}

    try:
        inicio = datetime.fromisoformat(fecha_inicio)
        if timezone.is_naive(inicio):
            inicio = timezone.make_aware(inicio, timezone.get_current_timezone())
    except (ValueError, TypeError):
        return {'ok': False, 'mensaje': 'La fecha/hora no es válida. Usá formato YYYY-MM-DDTHH:MM.'}

    # El servicio debe ser uno de los que creó ESE profesional. Si el id no corresponde
    # (el modelo suele alucinarlo), se intenta resolver por nombre contra la descripción.
    servicio = _resolver_servicio(profesional_id, servicio_id, descripcion)

    # Validar SIEMPRE la agenda: el horario pedido debe estar libre en la disponibilidad real.
    from empresas.models import Horarios
    from disponibilidad.utils import rango_horario_empresa, hay_conflicto
    empresa = profesional.empresas_administradas.first()
    if empresa and not empresa.vende_servicios:
        return {'ok': False, 'no_toma_turnos': True,
                'mensaje': 'Este negocio vende productos y no toma turnos. Ofrecé hacer un pedido en su lugar.'}

    # Si es profesional de servicios y no se resolvió el servicio NI hay descripción,
    # no creamos a ciegas: pedimos que elija uno de la lista (evita reservas sin servicio).
    if empresa and empresa.vende_servicios and servicio is None and not (descripcion or '').strip():
        opciones = list(Servicio.objects.filter(usuario_id=profesional_id).values('id', 'nombre', 'precio'))
        if opciones:
            return {'ok': False, 'falta_servicio': True, 'opciones': opciones,
                    'mensaje': ('Falta indicar el servicio. Volvé a llamar con el `servicio_id` EXACTO '
                                'de esta lista (o el nombre del servicio en `descripcion`).')}

    if empresa and Horarios.objects.filter(empresa=empresa, enabled=True).exists():
        dur = (servicio.tiempo if servicio else
               (Servicio.objects.filter(usuario_id=profesional_id)
                .order_by('tiempo').values_list('tiempo', flat=True).first()) or 60)
        rango = rango_horario_empresa(profesional, inicio)
        fin_slot = inicio + timedelta(minutes=dur)
        libre = (bool(rango) and rango[0] <= inicio and fin_slot <= rango[1]
                 and not hay_conflicto(profesional.id, inicio, fin_slot))
        if not libre:
            return {'ok': False, 'no_disponible': True,
                    'fecha_pedida': inicio.isoformat(),
                    'mensaje': ('Ese día/hora NO está disponible en la agenda del profesional. '
                                'Consultá disponibilidad_profesional y ofrecé un horario libre.')}

    # Domicilio: sólo si el servicio lo acepta (o no hay servicio) Y el cliente lo pidió.
    acepta_dom = servicio.acepta_domicilio if servicio else True
    quiere_domicilio = bool(es_domicilio) and acepta_dom
    if quiere_domicilio:
        if not direccion:
            return {'ok': False, 'necesita_direccion': True,
                    'mensaje': 'Para un trabajo a domicilio necesito la dirección exacta del cliente. Pedísela y volvé a llamar.'}
        loc = _localizacion_domicilio(conv, direccion)
        es_domicilio_profesional = False
    else:
        loc = _localizacion_profesional(profesional)
        es_domicilio_profesional = True

    cliente, tel_invitado = _resolver_cliente(conv)

    partes = []
    if descripcion:
        partes.append(descripcion)
    if tel_invitado:
        partes.append(f'[Invitado WhatsApp — tel: {tel_invitado}]')
    comentario = '\n'.join(partes)

    trabajo = Trabajo.objects.create(
        usuario=cliente,
        profesional=profesional,
        descripcion=(servicio.nombre if servicio else (descripcion or 'Reserva vía WhatsApp')),
        comentario_cliente=comentario,
        fecha_inicio=inicio,
        status='pendiente',
        metodo_pago=metodo_pago,
        precio_final=(servicio.precio if servicio else None),
        currency=((servicio.divisa or '')[:3] if servicio else None),
        localizacion=loc,
        es_domicilio_profesional=es_domicilio_profesional,
        phoneNumberInvitedUser=tel_invitado,
    )
    if servicio:
        TrabajoServicio.objects.create(trabajo=trabajo, servicio=servicio, precio=servicio.precio)

    conv.estado = conv.ESTADO_IDLE
    conv.save(update_fields=['estado', 'ultima_actividad'])

    # Avisar al profesional con el template de botón (confirmar/rechazar por link).
    try:
        from trabajos.tasks import enviar_template_confirmacion_trabajo_task
        enviar_template_confirmacion_trabajo_task.delay(trabajo.id)
    except Exception:
        logger.exception("No se pudo encolar el template de confirmación para trabajo %s", trabajo.id)

    return {
        'ok': True, 'trabajo_id': trabajo.id, 'status': trabajo.status,
        'profesional': f"{profesional.nombre} {profesional.apellido}".strip(),
        'servicio': servicio.nombre if servicio else None,
        'lugar': 'domicilio del cliente' if quiere_domicilio else 'local del profesional',
        'invitado': bool(tel_invitado),
        'fecha_inicio': inicio.isoformat(),
        'mensaje': 'Reserva creada como pendiente. El profesional debe confirmarla.',
    }


# ---------------------------------------------------------------------------
# Tools de escritura — pedidos (Carrito/Orden)
# ---------------------------------------------------------------------------
def agregar_item_pedido(conv, empresa_id, producto_id, cantidad=1, variante_id=None):
    from empresas.models import Producto, ProductoVariante
    producto = Producto.objects.filter(id=producto_id, empresa_id=empresa_id).first()
    if not producto:
        return {'ok': False, 'mensaje': 'Ese producto no existe en el negocio indicado.'}
    if producto.agotado:
        return {'ok': False, 'mensaje': f'{producto.nombre} está agotado.'}

    variante = None
    if variante_id:
        variante = ProductoVariante.objects.filter(id=variante_id, producto=producto, activo=True).first()

    pedido = conv.slots.get('pedido') or {}
    if pedido.get('empresa_id') and pedido['empresa_id'] != int(empresa_id):
        return {'ok': False, 'mensaje': 'Ya hay un pedido en curso de otro negocio. Confirmá o cancelá ese primero.'}
    pedido.setdefault('empresa_id', int(empresa_id))
    pedido.setdefault('items', [])

    precio_extra = float(variante.precio_extra) if variante else 0.0
    precio_unit = float(producto.precio) + precio_extra
    pedido['items'].append({
        'producto_id': producto.id, 'nombre': producto.nombre, 'cantidad': int(cantidad),
        'precio_unitario': precio_unit, 'variante_id': variante.id if variante else None,
        'variante_nombre': variante.nombre if variante else '', 'variante_precio_extra': precio_extra,
    })
    conv.slots['pedido'] = pedido
    conv.estado = conv.ESTADO_ARMANDO_PEDIDO
    conv.save(update_fields=['slots', 'estado', 'ultima_actividad'])
    total = sum(i['precio_unitario'] * i['cantidad'] for i in pedido['items'])
    return {'ok': True, 'items_en_pedido': len(pedido['items']), 'total_parcial': round(total, 2)}


def ver_pedido(conv):
    pedido = conv.slots.get('pedido')
    if not pedido or not pedido.get('items'):
        return {'ok': True, 'vacio': True, 'items': []}
    total = sum(i['precio_unitario'] * i['cantidad'] for i in pedido['items'])
    return {'ok': True, 'empresa_id': pedido['empresa_id'], 'items': pedido['items'], 'total': round(total, 2)}


def confirmar_pedido(conv, tipo_entrega, metodo_pago, notas='', direccion=None):
    from empresas.models import Empresa
    from carritos.models import Orden, OrdenItem

    pedido = conv.slots.get('pedido')
    if not pedido or not pedido.get('items'):
        return {'ok': False, 'mensaje': 'No hay items en el pedido.'}
    empresa = Empresa.objects.filter(id=pedido['empresa_id']).first()
    if not empresa:
        return {'ok': False, 'mensaje': 'El negocio del pedido ya no está disponible.'}
    if tipo_entrega not in ('retiro', 'domicilio'):
        return {'ok': False, 'mensaje': 'tipo_entrega debe ser "retiro" o "domicilio".'}
    if metodo_pago not in ('efectivo', 'tarjeta', 'transferencia', 'mercadopago', 'app'):
        return {'ok': False, 'mensaje': 'metodo_pago inválido.'}

    # Envío a domicilio → necesitamos la dirección exacta del cliente.
    loc_entrega = None
    if tipo_entrega == 'domicilio':
        if not direccion:
            return {'ok': False, 'necesita_direccion': True,
                    'mensaje': 'Para envío a domicilio necesito la dirección exacta del cliente. Pedísela y volvé a llamar.'}
        loc_entrega = _localizacion_domicilio(conv, direccion)

    cliente, tel_invitado = _resolver_cliente(conv)
    total = sum(Decimal(str(i['precio_unitario'])) * i['cantidad'] for i in pedido['items'])

    if metodo_pago == 'efectivo':
        pago_status = 'pago_en_domicilio' if tipo_entrega == 'domicilio' else 'pendiente'
    elif metodo_pago == 'transferencia':
        pago_status = 'pendiente'
    else:
        pago_status = 'pendiente'

    notas_final = notas or ''
    if tel_invitado:
        notas_final = (notas_final + f'\n[Invitado WhatsApp — tel: {tel_invitado}]').strip()

    orden = Orden.objects.create(
        usuario=cliente, empresa=empresa, metodo_pago=metodo_pago, tipo_entrega=tipo_entrega,
        total=total, notas=notas_final, pago_status=pago_status, currency=empresa.currency,
        localizacion_entrega=loc_entrega, phoneNumberInvitedUser=tel_invitado,
    )
    for i in pedido['items']:
        precio_unit = Decimal(str(i['precio_unitario']))
        OrdenItem.objects.create(
            orden=orden, producto_id=i['producto_id'], cantidad=i['cantidad'],
            precio_unitario=precio_unit, subtotal=precio_unit * i['cantidad'],
            variante_nombre=i.get('variante_nombre', ''),
            variante_precio_extra=Decimal(str(i.get('variante_precio_extra', 0))),
        )

    conv.slots.pop('pedido', None)
    conv.estado = conv.ESTADO_IDLE
    conv.save(update_fields=['slots', 'estado', 'ultima_actividad'])
    return {'ok': True, 'numero_orden': orden.numero_orden, 'total': str(orden.total),
            'entrega': tipo_entrega, 'invitado': bool(tel_invitado),
            'mensaje': f'Pedido {orden.numero_orden} registrado en {empresa.nombre}.'}


# ---------------------------------------------------------------------------
# Tools de escritura — onboarding profesional
# ---------------------------------------------------------------------------
_DIAS_MAP = {'lunes': 1, 'martes': 2, 'miercoles': 3, 'miércoles': 3, 'jueves': 4,
             'viernes': 5, 'sabado': 6, 'sábado': 6, 'domingo': 7}


def _onb(conv):
    return dict((conv.slots or {}).get('onboarding') or {})


def _save_onb(conv, data):
    slots = dict(conv.slots or {})
    slots['onboarding'] = data
    conv.slots = slots
    conv.save(update_fields=['slots', 'ultima_actividad'])


def _parse_hora(hhmm):
    return datetime.strptime(str(hhmm).strip(), '%H:%M').time()


def _normalizar_dias(dias):
    if isinstance(dias, (int, str)):
        dias = [dias]
    out = []
    for d in dias or []:
        if isinstance(d, int):
            out.append(d)
        elif str(d).strip().isdigit():
            out.append(int(d))
        else:
            k = str(d).strip().lower()
            if k in _DIAS_MAP:
                out.append(_DIAS_MAP[k])
    return sorted(set(x for x in out if 1 <= x <= 7))


_ONB_BASICOS = ('nombre', 'apellido', 'correo', 'telefono')


def _modalidad_flags(modalidad):
    m = (modalidad or 'ambos').strip().lower()
    if m not in ('domicilio', 'local', 'ambos'):
        m = 'ambos'
    return m, (m in ('domicilio', 'ambos')), (m in ('local', 'ambos'))


def _onb_faltan_basicos(data):
    faltan = [c for c in _ONB_BASICOS if not str(data.get(c) or '').strip()]
    if data.get('vende_productos') is None and data.get('vende_servicios') is None:
        faltan.append('vende_productos/vende_servicios')
    return faltan


def _guard_basicos(conv):
    """Impide cargar servicios/productos/horarios/localización sin los datos básicos completos."""
    faltan = _onb_faltan_basicos(_onb(conv))
    if faltan:
        return {'ok': False, 'orden_incorrecto': True, 'faltan_basicos': faltan,
                'mensaje': ('Todavía NO cargues esto. Primero completá los datos básicos con '
                            'onboarding_datos, pidiéndolos de a UNO. Falta: ' + ', '.join(faltan) + '.')}
    return None


def iniciar_onboarding_profesional(conv):
    conv.flujo = conv.FLUJO_ONBOARDING_PROFESIONAL
    conv.estado = conv.ESTADO_RECOLECTANDO_DATOS_PROF
    slots = dict(conv.slots or {})
    slots['onboarding'] = {'servicios': [], 'productos': [], 'horarios': []}
    conv.slots = slots
    conv.save(update_fields=['flujo', 'estado', 'slots', 'ultima_actividad'])
    return {'ok': True, 'siguiente': 'nombre',
            'mensaje': ('Alta iniciada. PASO 1 (obligatorio, en orden): pedí de a UNO y guardá con '
                        'onboarding_datos → nombre, luego apellido, luego correo, luego teléfono. '
                        'NO avances al siguiente dato sin haber guardado el anterior. Recién después '
                        'preguntá si vende productos, servicios o ambos.')}


def onboarding_datos(conv, nombre=None, apellido=None, correo=None, telefono=None,
                     profesion=None, vende_productos=None, vende_servicios=None, nombre_empresa=None):
    """Guarda/actualiza los datos básicos. Llamala tras CADA dato que te dé el usuario."""
    from usuario.models import Usuario
    data = _onb(conv)
    if correo and Usuario.objects.filter(correo__iexact=correo.strip()).exists():
        return {'ok': False, 'mensaje': 'Ese correo ya está registrado. Pedí otro.'}
    for k, v in (('nombre', nombre), ('apellido', apellido), ('correo', correo),
                 ('telefono', telefono), ('profesion', profesion), ('nombre_empresa', nombre_empresa)):
        if v is not None:
            data[k] = v
    if vende_productos is not None:
        data['vende_productos'] = bool(vende_productos)
    if vende_servicios is not None:
        data['vende_servicios'] = bool(vende_servicios)
    for lst in ('servicios', 'productos', 'horarios'):
        data.setdefault(lst, [])
    _save_onb(conv, data)
    faltan = _onb_faltan_basicos(data)
    if faltan:
        siguiente = faltan[0]
    elif not (data['servicios'] or data['productos']):
        siguiente = 'cargar servicios y/o productos'
    else:
        siguiente = 'horarios y localización'
    return {'ok': True, 'faltan_basicos': faltan, 'siguiente': siguiente,
            'datos': {k: data.get(k) for k in ('nombre', 'apellido', 'correo', 'telefono',
                                               'profesion', 'nombre_empresa',
                                               'vende_productos', 'vende_servicios')}}


def onboarding_agregar_servicio(conv, nombre, precio, tiempo_min, modalidad='ambos', profesion=None):
    """Agrega/actualiza UN servicio. `modalidad`: 'domicilio' | 'local' | 'ambos'."""
    g = _guard_basicos(conv)
    if g:
        return g
    data = _onb(conv)
    if not data.get('vende_servicios'):
        return {'ok': False, 'mensaje': 'Marcá vende_servicios=true en onboarding_datos antes de cargar servicios.'}
    modalidad, _, _ = _modalidad_flags(modalidad)
    servicios = data.setdefault('servicios', [])
    nombre_n = str(nombre).strip().lower()
    item = {'nombre': nombre, 'precio': str(precio), 'tiempo_min': int(tiempo_min),
            'profesion': profesion or data.get('profesion'), 'modalidad': modalidad}
    for s in servicios:  # dedupe por nombre: actualiza en vez de duplicar
        if (s.get('nombre') or '').strip().lower() == nombre_n:
            s.update(item)
            _save_onb(conv, data)
            return {'ok': True, 'actualizado': True, 'servicios': servicios}
    servicios.append(item)
    _save_onb(conv, data)
    return {'ok': True, 'servicios': servicios}


def onboarding_agregar_producto(conv, nombre, precio, descripcion=''):
    """Agrega/actualiza UN producto (dedupe por nombre)."""
    g = _guard_basicos(conv)
    if g:
        return g
    data = _onb(conv)
    if not data.get('vende_productos'):
        return {'ok': False, 'mensaje': 'Marcá vende_productos=true en onboarding_datos antes de cargar productos.'}
    productos = data.setdefault('productos', [])
    nombre_n = str(nombre).strip().lower()
    item = {'nombre': nombre, 'precio': str(precio), 'descripcion': descripcion or ''}
    for p in productos:
        if (p.get('nombre') or '').strip().lower() == nombre_n:
            p.update(item)
            _save_onb(conv, data)
            return {'ok': True, 'actualizado': True, 'productos': productos}
    productos.append(item)
    _save_onb(conv, data)
    return {'ok': True, 'productos': productos}


def onboarding_agregar_horario(conv, dias, hora_inicio, hora_fin):
    """dias: lista de días (1=lunes..7=domingo o nombres). hora_inicio/fin: 'HH:MM'."""
    g = _guard_basicos(conv)
    if g:
        return g
    try:
        _parse_hora(hora_inicio); _parse_hora(hora_fin)
    except (ValueError, TypeError):
        return {'ok': False, 'mensaje': 'Horas inválidas. Usá formato HH:MM (ej. 09:00).'}
    dias_norm = _normalizar_dias(dias)
    if not dias_norm:
        return {'ok': False, 'mensaje': 'Indicá los días (ej. lunes a viernes) como 1..7.'}
    data = _onb(conv)
    horarios = data.setdefault('horarios', [])
    for h in horarios:  # dedupe exacto
        if h.get('dias') == dias_norm and h.get('inicio') == hora_inicio and h.get('fin') == hora_fin:
            return {'ok': True, 'duplicado_ignorado': True, 'horarios': horarios}
    horarios.append({'dias': dias_norm, 'inicio': hora_inicio, 'fin': hora_fin})
    _save_onb(conv, data)
    return {'ok': True, 'horarios': horarios}


def onboarding_localizacion(conv, zona):
    g = _guard_basicos(conv)
    if g:
        return g
    r = geo.geocode_texto(zona, pais=conv.pais or 'UY')
    if not r:
        return {'ok': False, 'mensaje': f'No pude ubicar "{zona}". Pedí una dirección/zona más simple.'}
    data = _onb(conv)
    data['localizacion'] = {'ubicacion': r.get('place_name') or zona, 'lat': r['lat'], 'lon': r['lon'],
                            'ciudad': r.get('ciudad', ''), 'pais': r.get('pais', '')}
    _save_onb(conv, data)
    return {'ok': True, 'ubicacion': data['localizacion']['ubicacion']}


def onboarding_resumen(conv):
    """Devuelve todo lo cargado para confirmar con el cliente antes de finalizar."""
    return {'ok': True, 'onboarding': _onb(conv)}


def finalizar_registro_profesional(conv):
    """Crea al profesional con TODOS los datos cargados (equivale al registro completo)."""
    import secrets
    from django.db import transaction
    from usuario.models import Usuario
    from profesion.models import Profesion
    from usuario_profesion.models import UsuarioProfesion
    from empresas.models import Horarios, Producto
    from empresas.utils import crear_empresa
    from servicios.models import Servicio
    from localizacion.models import Localizacion
    from usuario_localizacion.models import UsuarioLocalizacion

    d = _onb(conv)
    faltan = [c for c in _ONB_BASICOS if not str(d.get(c) or '').strip()]
    if faltan:
        return {'ok': False, 'faltan_basicos': faltan,
                'mensaje': f'Faltan datos básicos: {", ".join(faltan)}. Pedílos de a uno con onboarding_datos.'}
    if not d.get('localizacion'):
        return {'ok': False, 'mensaje': 'Falta la localización del profesional.'}
    vende_serv = bool(d.get('vende_servicios'))
    vende_prod = bool(d.get('vende_productos'))
    if not (vende_serv or vende_prod):
        return {'ok': False, 'mensaje': 'Indicá si vende productos, servicios o ambos.'}
    if vende_serv and not d.get('horarios'):
        return {'ok': False, 'mensaje': 'Un negocio de servicios necesita horarios cargados.'}
    if vende_serv and not d.get('servicios'):
        return {'ok': False, 'mensaje': 'Cargá al menos un servicio.'}
    if vende_prod and not d.get('productos'):
        return {'ok': False, 'mensaje': 'Cargá al menos un producto.'}
    if Usuario.objects.filter(correo__iexact=d['correo'].strip()).exists():
        return {'ok': False, 'mensaje': 'Ese correo ya está registrado.'}

    loc = d['localizacion']
    prof = _resolver_profesion(d.get('profesion')) if d.get('profesion') else None

    try:
        with transaction.atomic():
            usuario = Usuario.objects.create_user(
                correo=d['correo'].strip(), password=secrets.token_urlsafe(9),
                nombre=d['nombre'].strip()[:100], apellido=d['apellido'].strip()[:100],
                telefono=(d.get('telefono') or conv.wa_id or '')[:20],
                is_owner_empresa=True, is_configured=True, trabajo_local=True,
            )
            localizacion = Localizacion.objects.create(
                ubicacion=loc['ubicacion'], address=loc['ubicacion'],
                latitud=Decimal(str(loc['lat'])), longitud=Decimal(str(loc['lon'])),
                city=loc.get('ciudad', '') or '', county='', state='',
                country=loc.get('pais', '') or 'Uruguay', isPrimary=True)
            UsuarioLocalizacion.objects.create(usuario=usuario, localizacion=localizacion, es_principal=True)
            if prof:
                UsuarioProfesion.objects.get_or_create(usuario=usuario, profesion=prof)
            empresa = crear_empresa(
                nombre=(d.get('nombre_empresa') or f"{usuario.nombre} {usuario.apellido}").strip(),
                ubicacion=loc['ubicacion'], latitud=Decimal(str(loc['lat'])), longitud=Decimal(str(loc['lon'])),
                admin_id=usuario, descripcion='', unipersonal=True, localizacion=localizacion,
                vende_productos=vende_prod, vende_servicios=vende_serv, vende_menu_diario=False,
            )
            for s in d.get('servicios', []):
                sp = _resolver_profesion(s.get('profesion')) or prof
                if not sp:
                    continue
                _, acepta_dom, acepta_ret = _modalidad_flags(s.get('modalidad'))
                Servicio.objects.create(
                    usuario=usuario, profesion=sp, nombre=str(s['nombre'])[:200],
                    precio=Decimal(str(s['precio'])), divisa='UYU', tiempo=int(s['tiempo_min']),
                    acepta_domicilio=acepta_dom, acepta_retiro=acepta_ret)
            for p in d.get('productos', []):
                Producto.objects.create(
                    empresa=empresa, nombre=str(p['nombre'])[:200], precio=Decimal(str(p['precio'])),
                    divisa='UYU', descripcion=p.get('descripcion', '') or '', es_menu_diario=False)
            for h in d.get('horarios', []):
                for dia in h.get('dias', []):
                    Horarios.objects.create(
                        empresa=empresa, dia_semana=str(dia),
                        hora_inicio=_parse_hora(h['inicio']), hora_fin=_parse_hora(h['fin']), enabled=True)
    except Exception as exc:  # noqa: BLE001
        logger.exception('finalizar_registro_profesional falló')
        return {'ok': False, 'mensaje': f'No pude completar el registro: {exc}'}

    conv.usuario = usuario
    conv.flujo = conv.FLUJO_CLIENTE
    conv.estado = conv.ESTADO_IDLE
    slots = dict(conv.slots or {})
    slots.pop('onboarding', None)
    conv.slots = slots
    conv.save(update_fields=['usuario', 'flujo', 'estado', 'slots', 'ultima_actividad'])
    return {'ok': True, 'usuario_id': usuario.id, 'empresa_id': empresa.id,
            'profesion': prof.nombre if prof else None,
            'servicios_creados': len(d.get('servicios', [])),
            'productos_creados': len(d.get('productos', [])),
            'mensaje': 'Profesional registrado con éxito.'}


# ---------------------------------------------------------------------------
# Registro / dispatch
# ---------------------------------------------------------------------------
REGISTRY = {
    'set_ubicacion': set_ubicacion,
    'buscar': buscar,
    'detalle_negocio': detalle_negocio,
    'listar_productos': listar_productos,
    'menu_del_dia': menu_del_dia,
    'listar_servicios_profesional': listar_servicios_profesional,
    'disponibilidad_profesional': disponibilidad_profesional,
    'crear_reserva': crear_reserva,
    'agregar_item_pedido': agregar_item_pedido,
    'ver_pedido': ver_pedido,
    'confirmar_pedido': confirmar_pedido,
    'iniciar_onboarding_profesional': iniciar_onboarding_profesional,
    'onboarding_datos': onboarding_datos,
    'onboarding_agregar_servicio': onboarding_agregar_servicio,
    'onboarding_agregar_producto': onboarding_agregar_producto,
    'onboarding_agregar_horario': onboarding_agregar_horario,
    'onboarding_localizacion': onboarding_localizacion,
    'onboarding_resumen': onboarding_resumen,
    'finalizar_registro_profesional': finalizar_registro_profesional,
}


def make_dispatch(conv):
    def dispatch(nombre, args):
        fn = REGISTRY.get(nombre)
        if not fn:
            return {'error': f'Herramienta desconocida: {nombre}'}
        return fn(conv, **args)
    return dispatch


def _tool(name, description, properties, required):
    return {
        'type': 'function',
        'function': {
            'name': name,
            'description': description,
            'parameters': {'type': 'object', 'properties': properties, 'required': required},
        },
    }


TOOL_SPECS = [
    _tool('set_ubicacion', 'Fija la ubicación del usuario a partir de una zona/ciudad/dirección en texto.',
          {'zona': {'type': 'string', 'description': 'Zona, barrio, ciudad o dirección.'}}, ['zona']),
    _tool('buscar',
          'Búsqueda unificada de profesionales, negocios, servicios y productos cercanos a la '
          'ubicación del usuario, ordenados por cercanía. Usá `termino` con lo que pide el usuario '
          '(ej. "cerrajero", "milanesas", "corte de pelo"). Si mapeás el pedido a una profesión del '
          'catálogo, pasala en `profesion` para filtrar mejor. Devuelve datos reales: NO inventes.',
          {'termino': {'type': 'string', 'description': 'Texto a buscar (servicio, producto, oficio, nombre).'},
           'tipo': {'type': 'string', 'enum': ['profesionales', 'negocios', 'servicios', 'productos'],
                    'description': 'Opcional: limitar el tipo de resultado.'},
           'profesion': {'type': 'string', 'description': 'Nombre EXACTO de una profesión del catálogo, si aplica.'},
           'radio_km': {'type': 'number'},
           'limite': {'type': 'integer'}}, []),
    _tool('detalle_negocio', 'Devuelve info detallada y horarios de un negocio (por empresa_id de una búsqueda).',
          {'empresa_id': {'type': 'integer'}}, ['empresa_id']),
    _tool('listar_productos', 'Lista productos (catálogo) de un negocio.',
          {'empresa_id': {'type': 'integer'}, 'buscar': {'type': 'string'}, 'limite': {'type': 'integer'}}, ['empresa_id']),
    _tool('menu_del_dia', 'Lista los platos del menú diario de un negocio para un día (1=lunes..7=domingo).',
          {'empresa_id': {'type': 'integer'}, 'dia_semana': {'type': 'integer'}}, ['empresa_id']),
    _tool('listar_servicios_profesional', 'Lista los servicios que ofrece un profesional.',
          {'profesional_id': {'type': 'integer'}}, ['profesional_id']),
    _tool('disponibilidad_profesional', 'Consulta tramos de disponibilidad de un profesional (opcional fecha YYYY-MM-DD).',
          {'profesional_id': {'type': 'integer'}, 'fecha': {'type': 'string'}}, ['profesional_id']),
    _tool('crear_reserva',
          'Crea una reserva/turno con un profesional. Confirmá con el usuario antes de llamar. '
          'Elegí `servicio_id` de los que ofrece ese profesional (usá listar_servicios_profesional); '
          'si ninguno aplica, dejá servicio_id vacío y poné lo que pide el cliente en `descripcion`. '
          'Poné `es_domicilio=true` sólo si el trabajo es en la casa del cliente: en ese caso ANTES '
          'pedí la `direccion` exacta. Si no es a domicilio, el trabajo es en el local del profesional.',
          {'profesional_id': {'type': 'integer'}, 'fecha_inicio': {'type': 'string', 'description': 'ISO YYYY-MM-DDTHH:MM'},
           'servicio_id': {'type': 'integer', 'description': 'Id de un servicio del profesional (opcional).'},
           'descripcion': {'type': 'string', 'description': 'Lo que pide el cliente (sobre todo si no hay servicio).'},
           'es_domicilio': {'type': 'boolean', 'description': 'true si el trabajo es en el domicilio del cliente.'},
           'direccion': {'type': 'string', 'description': 'Dirección exacta del cliente (requerida si es_domicilio=true).'},
           'metodo_pago': {'type': 'string'}},
          ['profesional_id', 'fecha_inicio']),
    _tool('agregar_item_pedido', 'Agrega un producto al pedido en curso.',
          {'empresa_id': {'type': 'integer'}, 'producto_id': {'type': 'integer'},
           'cantidad': {'type': 'integer'}, 'variante_id': {'type': 'integer'}},
          ['empresa_id', 'producto_id']),
    _tool('ver_pedido', 'Muestra el pedido en curso y su total.', {}, []),
    _tool('confirmar_pedido',
          'Confirma y crea la orden del pedido en curso. Confirmá con el usuario antes de llamar. '
          'Si tipo_entrega="domicilio", ANTES pedí la `direccion` exacta del cliente.',
          {'tipo_entrega': {'type': 'string', 'enum': ['retiro', 'domicilio']},
           'metodo_pago': {'type': 'string', 'enum': ['efectivo', 'tarjeta', 'transferencia', 'mercadopago']},
           'direccion': {'type': 'string', 'description': 'Dirección exacta del cliente (requerida si tipo_entrega=domicilio).'},
           'notas': {'type': 'string'}},
          ['tipo_entrega', 'metodo_pago']),
    _tool('iniciar_onboarding_profesional',
          'Inicia el alta de un usuario que quiere ofrecer sus servicios/productos como profesional. '
          'Llamala apenas el usuario dice que quiere registrarse.', {}, []),
    _tool('onboarding_datos',
          'Guarda los datos básicos del profesional durante el alta. Pedilos de a uno. '
          '`vende_productos`/`vende_servicios` según lo que ofrezca (pueden ser ambos).',
          {'nombre': {'type': 'string'}, 'apellido': {'type': 'string'}, 'correo': {'type': 'string'},
           'telefono': {'type': 'string'}, 'profesion': {'type': 'string', 'description': 'Profesión del catálogo.'},
           'vende_productos': {'type': 'boolean'}, 'vende_servicios': {'type': 'boolean'},
           'nombre_empresa': {'type': 'string'}}, []),
    _tool('onboarding_agregar_servicio',
          'Agrega UN servicio del profesional (una vez por servicio; si repetís el nombre, lo actualiza). '
          'Preguntá SIEMPRE la modalidad: si lo hace a domicilio, en el local, o ambos.',
          {'nombre': {'type': 'string'}, 'precio': {'type': 'number'}, 'tiempo_min': {'type': 'integer'},
           'modalidad': {'type': 'string', 'enum': ['domicilio', 'local', 'ambos'],
                         'description': '¿El servicio es a domicilio, en el local, o ambos?'},
           'profesion': {'type': 'string'}}, ['nombre', 'precio', 'tiempo_min']),
    _tool('onboarding_agregar_producto',
          'Agrega UN producto que vende el profesional (llamala una vez por cada producto).',
          {'nombre': {'type': 'string'}, 'precio': {'type': 'number'}, 'descripcion': {'type': 'string'}},
          ['nombre', 'precio']),
    _tool('onboarding_agregar_horario',
          'Agrega un tramo de horario de atención. `dias` es lista 1..7 (1=lunes). Ej: dias=[1,2,3,4,5], 09:00-18:00.',
          {'dias': {'type': 'array', 'items': {'type': 'integer'}},
           'hora_inicio': {'type': 'string', 'description': 'HH:MM'}, 'hora_fin': {'type': 'string', 'description': 'HH:MM'}},
          ['dias', 'hora_inicio', 'hora_fin']),
    _tool('onboarding_localizacion', 'Fija la localización del profesional a partir de una dirección/zona en texto.',
          {'zona': {'type': 'string'}}, ['zona']),
    _tool('onboarding_resumen', 'Devuelve todo lo cargado para confirmarlo con el usuario antes de finalizar.', {}, []),
    _tool('finalizar_registro_profesional',
          'Crea al profesional con todos los datos cargados. Llamala SOLO tras confirmar el resumen. '
          'Devuelve error si falta algo (datos, localización, horarios de servicios, etc.).', {}, []),
]
