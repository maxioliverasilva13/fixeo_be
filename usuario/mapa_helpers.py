"""
Consultas optimizadas para pins del mapa (top-zona, rango-mapa, top-nacionales).
Evita listar miles de filas en bbox grande y N+1 en serialización.

Orden por defecto de pins: mejor plan activo (precio del plan, luego cantidad_jobs),
luego criterio del filtro (rating, distancia o precio).
"""
from __future__ import annotations

import datetime
import math
from datetime import timedelta
from decimal import Decimal

from django.db.models import Avg, Count, DecimalField, F, IntegerField, Min, OuterRef, Prefetch, Subquery
from django.utils import timezone

from empresas.models import Empresa, Horarios
from usuario.models import Usuario
from usuario.serializers import UsuarioInMapaSerializer
from usuario_localizacion.models import UsuarioLocalizacion
from usuario_profesion.models import UsuarioProfesion

MAP_BOUNDS_MAX_SCAN_DEFAULT = 400
MAP_BOUNDS_MAX_SCAN_WIDE = 220
MAP_NATIONAL_MAX_SCAN = 1200
MAP_NATIONAL_BATCH_SIZE = 150


def _active_plan_precio_subquery():
    from suscripciones.models import Subscripcion

    now = timezone.now()
    return Subscripcion.objects.filter(
        user_id=OuterRef('pk'),
        cancelada=False,
        expiracion__gt=now,
    ).order_by(
        '-plan_id__precio',
        '-plan_id__cantidad_jobs',
        '-created_at',
    ).values('plan_id__precio')[:1]


def _active_plan_jobs_subquery():
    from suscripciones.models import Subscripcion

    now = timezone.now()
    return Subscripcion.objects.filter(
        user_id=OuterRef('pk'),
        cancelada=False,
        expiracion__gt=now,
    ).order_by(
        '-plan_id__precio',
        '-plan_id__cantidad_jobs',
        '-created_at',
    ).values('plan_id__cantidad_jobs')[:1]


def annotate_map_plan_rank(qs):
    """Plan activo más alto por usuario (para ordenar antes de visibilidad/serializar)."""
    return qs.annotate(
        active_plan_precio=Subquery(
            _active_plan_precio_subquery(),
            output_field=DecimalField(max_digits=10, decimal_places=2),
        ),
        active_plan_jobs=Subquery(
            _active_plan_jobs_subquery(),
            output_field=IntegerField(),
        ),
    )


def plan_rank_tuple_from_sub(sub) -> tuple[float, int]:
    if not sub:
        return (0.0, 0)
    return (float(sub.plan_id.precio), int(sub.plan_id.cantidad_jobs))


def plan_rank_tuple_from_usuario(usuario) -> tuple[float, int]:
    precio = getattr(usuario, 'active_plan_precio', None)
    jobs = getattr(usuario, 'active_plan_jobs', None)
    if precio is not None:
        return (float(precio), int(jobs or 0))
    return (0.0, 0)


def sort_map_result_rows(results: list[dict], sort_by: str, subs_map: dict) -> None:
    """
    Orden de pins: (1) mejor plan, (2) sort_by del cliente.
    mejor_valorados → rating; mas_cercanos → distancia; mejor_precio → precio mínimo.
    """

    def sort_key(row: dict) -> tuple:
        usuario = row['usuario']
        sub = subs_map.get(usuario.id)
        plan_p, plan_j = plan_rank_tuple_from_sub(sub)
        if plan_p == 0.0:
            plan_p, plan_j = plan_rank_tuple_from_usuario(usuario)

        if sort_by == 'mas_cercanos':
            return (-plan_p, -plan_j, row.get('distance_km', 0.0))
        if sort_by == 'mejor_precio':
            mp = row.get('min_price')
            return (-plan_p, -plan_j, mp is None, mp if mp is not None else 0)
        # mejor_valorados (default)
        return (-plan_p, -plan_j, -row.get('avg_rating', 0.0))

    results.sort(key=sort_key)


def batch_visibility_data(user_ids: list):
    from suscripciones.models import Subscripcion
    from trabajos.models import Trabajo

    if not user_ids:
        return {}, {}

    now = timezone.now()
    subs_map = {}
    for sub in (
        Subscripcion.objects
        .filter(user_id__in=user_ids, cancelada=False, expiracion__gt=now)
        .select_related('plan_id')
        .order_by('-plan_id__precio', '-plan_id__cantidad_jobs', '-created_at')
    ):
        uid = sub.user_id_id
        if uid not in subs_map:
            subs_map[uid] = sub

    hace_30_dias = now - timedelta(days=30)
    efectivo_counts = dict(
        Trabajo.objects
        .filter(
            profesional__in=user_ids,
            metodo_pago='efectivo',
            created_at__gte=hace_30_dias,
            is_deleted=False,
        )
        .exclude(status='cancelado')
        .values('profesional')
        .annotate(cnt=Count('id'))
        .values_list('profesional', 'cnt')
    )
    return subs_map, efectivo_counts


def es_visible_en_mapa(usuario, subs_map: dict, efectivo_counts: dict) -> bool:
    emps = getattr(usuario, '_prefetched_objects_cache', {}).get('empresas_administradas')
    empresa = emps[0] if emps else usuario.empresas_administradas.first()
    if not empresa:
        return False

    if empresa.acepta_tarjeta and empresa.is_mercadopago_vinculado:
        return True

    if empresa.acepta_efectivo:
        sub = subs_map.get(usuario.id)
        if sub:
            usados = efectivo_counts.get(usuario.id, 0)
            jobs_restantes = max(0, sub.plan_id.cantidad_jobs - usados)
            if jobs_restantes > 0:
                return True

    return False


def _prefetch_empresas():
    return Prefetch(
        'empresas_administradas',
        queryset=Empresa.objects.all(),
    )


def _prefetch_localizaciones_primarias():
    return Prefetch(
        'localizaciones',
        queryset=UsuarioLocalizacion.objects.filter(
            localizacion__isPrimary=True,
        ).select_related('localizacion'),
        to_attr='localizaciones_primarias',
    )


MAP_USUARIO_PREFETCH = (
    Prefetch(
        'usuario_profesiones',
        queryset=UsuarioProfesion.objects.select_related('profesion'),
    ),
    _prefetch_localizaciones_primarias(),
    _prefetch_empresas(),
)


def max_scan_for_bounds(north, south, east, west, has_filters: bool) -> int:
    lat_span = abs(float(north) - float(south))
    lng_span = abs(float(east) - float(west))
    if lat_span > 6 or lng_span > 6:
        return MAP_BOUNDS_MAX_SCAN_WIDE if has_filters else 280
    if lat_span > 2 or lng_span > 2:
        return 320 if has_filters else MAP_BOUNDS_MAX_SCAN_DEFAULT
    return MAP_BOUNDS_MAX_SCAN_DEFAULT


def usuarios_mapa_queryset(user_ids: list[int]):
    if not user_ids:
        return Usuario.objects.none()
    return annotate_map_plan_rank(
        Usuario.objects.filter(id__in=user_ids).annotate(
            avg_rating=Avg('calificaciones_recibidas__rating'),
            min_precio_servicio=Min('servicios__precio'),
        )
    ).prefetch_related(*MAP_USUARIO_PREFETCH)


def build_horarios_por_empresa(empresa_ids: list[int]) -> dict[int, list[dict]]:
    if not empresa_ids:
        return {}

    now = timezone.localtime()
    dia_semana = str(now.weekday() + 1)
    hoy = now.date()
    tz = now.tzinfo

    rows = Horarios.objects.filter(
        empresa_id__in=empresa_ids,
        dia_semana=dia_semana,
        enabled=True,
    ).values('empresa_id', 'hora_inicio', 'hora_fin')

    out: dict[int, list[dict]] = {}
    for h in rows:
        eid = h['empresa_id']
        out.setdefault(eid, []).append({
            'hora_inicio': datetime.datetime.combine(
                hoy, h['hora_inicio'],
            ).replace(tzinfo=tz).isoformat(),
            'hora_fin': datetime.datetime.combine(
                hoy, h['hora_fin'],
            ).replace(tzinfo=tz).isoformat(),
        })
    return out


def serialize_usuarios_mapa(usuarios: list[Usuario]) -> list[dict]:
    if not usuarios:
        return []

    empresa_ids = []
    for u in usuarios:
        emps = getattr(u, '_prefetched_objects_cache', {}).get('empresas_administradas')
        if emps:
            empresa_ids.append(emps[0].id)

    context = {
        'horarios_por_empresa': build_horarios_por_empresa(empresa_ids),
    }
    return UsuarioInMapaSerializer(usuarios, many=True, context=context).data


def _distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return 6371 * 2 * math.asin(math.sqrt(a))


def bounds_usuarios_loc_qs(
    north,
    south,
    east,
    west,
    *,
    profesion_id=None,
    max_price=None,
    is_urgent=None,
):
    qs = (
        UsuarioLocalizacion.objects.filter(
            es_principal=True,
            localizacion__isPrimary=True,
            localizacion__latitud__lte=north,
            localizacion__latitud__gte=south,
            localizacion__longitud__lte=east,
            localizacion__longitud__gte=west,
            usuario__is_owner_empresa=True,
            usuario__is_active=True,
        )
        .select_related('usuario', 'localizacion')
    )

    if profesion_id:
        qs = qs.filter(usuario__usuario_profesiones__profesion_id=profesion_id)

    if max_price:
        qs = qs.annotate(
            min_price=Min('usuario__servicios__precio'),
        ).filter(min_price__lte=Decimal(max_price))

    if is_urgent == 'true':
        qs = qs.filter(usuario__trabajos_asignados__esUrgente=True)

    return qs.distinct().order_by('usuario_id')


def _national_scan_order(sort_by: str):
    """Orden SQL al escanear candidatos: plan primero, luego criterio del filtro."""
    plan_first = (
        F('active_plan_precio').desc(nulls_last=True),
        F('active_plan_jobs').desc(nulls_last=True),
    )
    if sort_by == 'mejor_precio':
        return (*plan_first, F('min_precio_servicio').asc(nulls_last=True), 'id')
    if sort_by == 'mas_cercanos':
        return (*plan_first, F('avg_rating').desc(nulls_last=True), 'id')
    return (*plan_first, F('avg_rating').desc(nulls_last=True), 'id')


def resolve_map_users_from_bounds(
    *,
    north,
    south,
    east,
    west,
    limit: int,
    sort_by: str,
    profesion_id=None,
    max_price=None,
    is_urgent=None,
) -> list[Usuario]:
    has_filters = bool(profesion_id or max_price or is_urgent == 'true')
    max_scan = max_scan_for_bounds(north, south, east, west, has_filters)

    loc_qs = bounds_usuarios_loc_qs(
        north, south, east, west,
        profesion_id=profesion_id,
        max_price=max_price,
        is_urgent=is_urgent,
    )[:max_scan]

    usuarios_list = list(loc_qs)
    if not usuarios_list:
        return []

    user_ids = list({ul.usuario_id for ul in usuarios_list})
    usuarios_by_id = {u.id: u for u in usuarios_mapa_queryset(user_ids)}
    subs_map, efectivo_counts = batch_visibility_data(user_ids)

    center_lat = float((north + south) / 2)
    center_lng = float((east + west) / 2)

    results = []
    for ul in usuarios_list:
        usuario = usuarios_by_id.get(ul.usuario_id)
        if not usuario or not es_visible_en_mapa(usuario, subs_map, efectivo_counts):
            continue

        lat = float(ul.localizacion.latitud)
        lng = float(ul.localizacion.longitud)
        avg_rating = float(usuario.avg_rating or 0)
        min_price = getattr(ul, 'min_price', None)
        if min_price is None and usuario.min_precio_servicio is not None:
            min_price = float(usuario.min_precio_servicio)

        results.append({
            'usuario': usuario,
            'distance_km': _distance_km(center_lat, center_lng, lat, lng),
            'avg_rating': avg_rating,
            'min_price': float(min_price) if min_price is not None else None,
        })

    sort_map_result_rows(results, sort_by, subs_map)
    return [r['usuario'] for r in results[:limit]]


def resolve_map_users_national(*, limit: int, sort_by: str) -> list[Usuario]:
    base_qs = annotate_map_plan_rank(
        Usuario.objects.filter(is_owner_empresa=True, is_active=True).annotate(
            avg_rating=Avg('calificaciones_recibidas__rating'),
        )
    )

    if sort_by == 'mejor_precio':
        base_qs = base_qs.annotate(min_precio_servicio=Min('servicios__precio'))

    queryset = base_qs.order_by(*_national_scan_order(sort_by))

    candidates: list[dict] = []
    offset = 0
    scanned = 0
    batch_size = min(MAP_NATIONAL_BATCH_SIZE, max(limit + 30, limit * 4))
    target_candidates = min(limit * 4, limit + 80)

    while len(candidates) < target_candidates and scanned < MAP_NATIONAL_MAX_SCAN:
        batch_ids = list(
            queryset.values_list('id', flat=True)[offset : offset + batch_size]
        )
        if not batch_ids:
            break
        scanned += len(batch_ids)
        offset += batch_size

        batch = list(usuarios_mapa_queryset(batch_ids))
        subs_map, efectivo_counts = batch_visibility_data(batch_ids)

        for u in batch:
            if not es_visible_en_mapa(u, subs_map, efectivo_counts):
                continue
            candidates.append({
                'usuario': u,
                'avg_rating': float(u.avg_rating or 0),
                'min_price': (
                    float(u.min_precio_servicio)
                    if getattr(u, 'min_precio_servicio', None) is not None
                    else None
                ),
                'distance_km': 0.0,
            })

    if not candidates:
        return []

    all_ids = [r['usuario'].id for r in candidates]
    subs_map, _ = batch_visibility_data(all_ids)
    sort_map_result_rows(candidates, sort_by, subs_map)
    return [r['usuario'] for r in candidates[:limit]]
