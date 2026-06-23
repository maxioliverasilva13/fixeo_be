from localizacion.utils import calcular_distancia_km


def obtener_zonas_activas(usuario):
    from .models import ZonaNoTrabajo

    return list(
        ZonaNoTrabajo.objects.filter(usuario=usuario, activa=True).only(
            'id', 'latitud', 'longitud', 'radio_km', 'nombre'
        )
    )


def punto_en_zona_exclusion(lat, lng, zonas) -> bool:
    if not zonas:
        return False

    for zona in zonas:
        dist = calcular_distancia_km(lat, lng, zona.latitud, zona.longitud)
        if dist <= float(zona.radio_km):
            return True
    return False


def filtrar_trabajos_fuera_zonas_exclusion(trabajo_ids, usuario):
    if not trabajo_ids:
        return []

    zonas = obtener_zonas_activas(usuario)
    if not zonas:
        return trabajo_ids

    from trabajos.models import Trabajo

    trabajos = Trabajo.objects.filter(id__in=trabajo_ids).select_related('localizacion')
    permitidos = []

    for trabajo in trabajos:
        loc = trabajo.localizacion
        if not loc or loc.latitud is None or loc.longitud is None:
            permitidos.append(trabajo.id)
            continue
        if not punto_en_zona_exclusion(loc.latitud, loc.longitud, zonas):
            permitidos.append(trabajo.id)

    orden = {tid: idx for idx, tid in enumerate(trabajo_ids)}
    return sorted(permitidos, key=lambda tid: orden.get(tid, 0))


def filtrar_profesionales_fuera_zonas_exclusion(profesional_ids, lat_trabajo, lng_trabajo):
    if not profesional_ids:
        return []

    from .models import ZonaNoTrabajo

    zonas_por_usuario = {}
    for zona in ZonaNoTrabajo.objects.filter(
        usuario_id__in=profesional_ids,
        activa=True,
    ).only('usuario_id', 'latitud', 'longitud', 'radio_km'):
        zonas_por_usuario.setdefault(zona.usuario_id, []).append(zona)

    resultado = []
    for pro_id in profesional_ids:
        if not punto_en_zona_exclusion(lat_trabajo, lng_trabajo, zonas_por_usuario.get(pro_id, [])):
            resultado.append(pro_id)
    return resultado


def ubicacion_bloqueada_por_zonas_profesional(profesional, latitud, longitud) -> bool:
    """True si el profesional marcó esa ubicación como zona de no trabajo."""
    if latitud is None or longitud is None:
        return False
    return punto_en_zona_exclusion(latitud, longitud, obtener_zonas_activas(profesional))


def mensaje_zona_no_atendida() -> str:
    return (
        'Este profesional no trabaja en tu zona. '
        'Podés elegir atención en su local si está disponible.'
    )


def validar_zona_dentro_cobertura(usuario, latitud, longitud, radio_km):
    from .utils import obtener_localizacion_usuario

    loc = obtener_localizacion_usuario(usuario)
    if not loc or loc.latitud is None or loc.longitud is None:
        return 'Configurá tu dirección principal antes de crear zonas de exclusión.'

    rango = float(usuario.rango_mapa_km or 10)
    radio = float(radio_km)

    if radio < 0.3:
        return 'El radio mínimo es 0.3 km.'
    if radio > rango:
        return f'El radio no puede superar tu área de cobertura ({rango} km).'

    dist_centro = calcular_distancia_km(loc.latitud, loc.longitud, latitud, longitud)
    if dist_centro + radio > rango + 0.05:
        return 'La zona debe quedar completamente dentro de tu área de cobertura.'

    return None
