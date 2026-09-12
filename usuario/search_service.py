"""Funciones reutilizables de búsqueda.

Extraen el núcleo de ``usuario.views.search`` / ``usuario.views.recomendados`` a
funciones puras para poder usar EXACTAMENTE la misma lógica desde el API REST y
desde el agente de WhatsApp (``whatsapp/agent/tools.py``).

Las constantes SQL (``SQL_QUERY``, ``SQL_REC_*``) y los helpers de orden/plan
siguen viviendo en ``usuario.views``; acá se importan de forma perezosa (dentro
de las funciones) para no crear un import circular con ese módulo.
"""
from django.db import connection

from localizacion.utils import calcular_distancia_km
from usuario.models import Usuario
from usuario.utils import foto_usuario_api
from usuario.mapa_helpers import (
    batch_visibility_data as _batch_visibility_data,
    es_elegible_en_busqueda as _es_elegible_en_busqueda,
)


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _anotar_distancia(results, lat, lng):
    """Agrega ``distancia_km`` a cada fila que tenga lat/lon; None si no tiene."""
    for r in results:
        rlat, rlng = r.get('latitud'), r.get('longitud')
        if rlat is not None and rlng is not None:
            r['distancia_km'] = round(calcular_distancia_km(lat, lng, float(rlat), float(rlng)), 2)
        else:
            r['distancia_km'] = None
    return results


def _postprocesar_visibilidad(results, filtrar_elegibles=True):
    """Aplica fotos y campos de plan. Si `filtrar_elegibles` (API), descarta usuarios
    no elegibles (medio de pago/suscripción); si es False (canal WhatsApp), NO filtra
    a nadie — solo se usa el plan para priorizar después."""
    for r in results:
        if 'foto_url' in r:
            r['foto_url'] = foto_usuario_api(r.get('foto_url'))
        if 'rounded_foto_url' in r:
            r['rounded_foto_url'] = foto_usuario_api(r.get('rounded_foto_url'))

    usuario_ids = [r['id'] for r in results if r.get('tipo') == 'usuario']
    all_owner_ids = list({r['id'] for r in results if r.get('id') is not None})
    subs_map, efectivo_counts = ({}, {})
    if all_owner_ids:
        subs_map, efectivo_counts = _batch_visibility_data(all_owner_ids)

    if filtrar_elegibles and usuario_ids:
        usuarios_qs = Usuario.objects.filter(id__in=usuario_ids).prefetch_related('empresas_administradas')
        visibles = {u.id for u in usuarios_qs if _es_elegible_en_busqueda(u, subs_map, efectivo_counts)}
        results = [r for r in results if r.get('tipo') != 'usuario' or r['id'] in visibles]

    return results, subs_map


def buscar_unificado(q, *, exclude_id=0, profesion_id=None, max_price=None,
                     is_urgent=None, sort_by=None, limit=50,
                     lat=None, lng=None, radio_km=None, filtrar_elegibles=True):
    """Búsqueda por similaridad (trigram) sobre usuarios/empresas/profesiones/productos.

    Reproduce ``usuario.views.search`` cuando se la llama sin lat/lng/radio (API).
    Si se pasan lat/lng (canal WhatsApp), agrega ``distancia_km`` y, con radio_km,
    filtra y ordena por cercanía. Devuelve una lista de filas (dicts).
    """
    from usuario.views import (
        SQL_QUERY, _search_plan_fields, _precio_para_filtro, _sort_search_results,
    )

    q = (q or '').strip()
    if not q:
        return []

    lim = max(1, min(int(limit), 100))
    fetch_limit = min(500, max(lim * 10, 300))
    like_q = f"%{q}%"
    exclude_id = int(exclude_id or 0)

    with connection.cursor() as cursor:
        cursor.execute(SQL_QUERY, [
            # usuario: rank (nombre/apellido usuario + empresa si tiene + profesión)
            q, q, q, q, q, q, q,
            # usuario: where
            exclude_id,
            q, like_q, q, like_q,
            q, like_q,
            q, like_q, q, like_q, q, like_q,
            q, like_q,
            # producto: rank + where
            q, q,
            exclude_id,
            q, q, q,
            like_q, like_q, like_q,
            fetch_limit,
        ])
        columns = [col[0] for col in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]

    results, subs_map = _postprocesar_visibilidad(results, filtrar_elegibles=filtrar_elegibles)

    for r in results:
        plan_rank, plan_nombre = _search_plan_fields(subs_map.get(r.get('id')))
        r['plan_rank'] = plan_rank
        r['plan_nombre'] = plan_nombre

    if profesion_id:
        pid = int(profesion_id)
        results = [r for r in results if pid in (r.get('profesion_ids') or [])]

    if max_price:
        mp = float(max_price)
        results = [r for r in results if _precio_para_filtro(r) is None or _precio_para_filtro(r) <= mp]

    if is_urgent in ('true', True):
        results = [r for r in results if r.get('es_urgente')]

    # Canal con ubicación (WhatsApp): filtra por radio y ordena por plan (sub activa
    # primero) y luego por cercanía.
    if lat is not None and lng is not None:
        results = _anotar_distancia(results, float(lat), float(lng))
        if radio_km is not None:
            results = [r for r in results
                       if r.get('distancia_km') is not None and r['distancia_km'] <= float(radio_km)]
            results.sort(key=lambda x: (-(int(x.get('plan_rank') or 0)), x['distancia_km']))
            return results[:lim]

    _sort_search_results(results, sort_by)
    return results[:lim]


def recomendados_cercanos(*, tipo='profesional', exclude_id=0, profesion_id=None,
                          limit=10, offset=0, lat=None, lng=None, radio_km=None,
                          filtrar_elegibles=True):
    """Feed sin texto (recomendados) por categoría, ordenado por cercanía.

    Reproduce ``usuario.views.recomendados``. Con radio_km (WhatsApp) filtra por
    distancia. Devuelve una lista de filas (dicts).
    """
    from usuario.views import (
        SQL_REC_POR_TIPO, SQL_REC_PROFESIONALES, _search_plan_fields,
    )

    lim = max(1, min(int(limit), 50))
    offset = max(0, int(offset))
    fetch_limit = min(500, max(lim * 10, 300, offset + lim))
    exclude_id = int(exclude_id or 0)

    tipo = (tipo or 'profesional').strip().lower()
    sql = SQL_REC_POR_TIPO.get(tipo, SQL_REC_PROFESIONALES)

    with connection.cursor() as cursor:
        cursor.execute(sql, [exclude_id, fetch_limit])
        columns = [col[0] for col in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]

    results, subs_map = _postprocesar_visibilidad(results, filtrar_elegibles=filtrar_elegibles)

    # Servicios: sólo de usuarios con suscripción activa (solo cuando se filtra por elegibilidad).
    if filtrar_elegibles:
        results = [
            r for r in results
            if r.get('tipo') != 'servicio' or subs_map.get(r.get('id')) is not None
        ]

    for r in results:
        plan_rank, plan_nombre = _search_plan_fields(subs_map.get(r.get('id')))
        r['plan_rank'] = plan_rank
        r['plan_nombre'] = plan_nombre

    if profesion_id:
        pid = int(profesion_id)
        results = [r for r in results if pid in (r.get('profesion_ids') or [])]

    mi_lat, mi_lng = _to_float(lat), _to_float(lng)
    if mi_lat is not None and mi_lng is not None:
        results = _anotar_distancia(results, mi_lat, mi_lng)
        if radio_km is not None:
            results = [r for r in results
                       if r.get('distancia_km') is not None and r['distancia_km'] <= float(radio_km)]
        results.sort(key=lambda x: (
            -(int(x.get('plan_rank') or 0)),
            x.get('distancia_km') is None,
            x.get('distancia_km') if x.get('distancia_km') is not None else 0.0,
        ))
    else:
        results.sort(key=lambda x: (
            -(int(x.get('plan_rank') or 0)),
            -float(x.get('rating') or 0),
        ))

    return results[offset:offset + lim]
