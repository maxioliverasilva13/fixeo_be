# utils.py o al inicio de tu views.py
from django.db import connection

from .models import Trabajo


def filtrar_trabajos_por_distancia_sql(
    trabajos_queryset,
    usuario,
    latitud_usuario,
    longitud_usuario,
    rango_km=None,
    *,
    solo_urgentes: bool = True,
):
    """
    Filtra trabajos por distancia usando SQL directo (Postgres).

    Calcula km entre la ubicación del usuario y la del trabajo con fórmula esférica
    equivalente a haversine, con clamp en acos() para evitar errores NUMERIC/float fuera de [-1, 1].

    Por defecto (solo_urgentes=True), en SQL solo se consideran filas trabajo esUrgente=True además del
    listado de IDs ya filtrados por el queryset (doble garantía ante joins / queryset mal armado).

    Devuelve IDs de trabajo que están dentro del radio permitido por fila:
    distancia_km <= COALESCE(radio_busqueda_km del trabajo, rango del usuario).
    """
    if latitud_usuario is None or longitud_usuario is None:
        return []

    trabajo_ids_ordered = dict.fromkeys(
        list(trabajos_queryset.values_list('id', flat=True))
    )
    trabajo_ids = list(trabajo_ids_ordered.keys())

    if not trabajo_ids:
        return []

    rango = rango_km or getattr(usuario, 'rango_mapa_km', 10) or 10

    placeholders = ','.join(['%s'] * len(trabajo_ids))

    ops = connection.ops
    urgente_sql = ''
    if solo_urgentes:
        col = ops.quote_name(Trabajo._meta.get_field('esUrgente').column)
        urgente_sql = f' AND t.{col} IS TRUE'

    query = f"""
    WITH trabajos_con_localizacion AS (
        SELECT
            t.id,
            t.radio_busqueda_km,
            l.latitud,
            l.longitud,
            (
                6371 * acos(
                    LEAST(1::float8, GREATEST(-1::float8,
                        cos(radians(%s::float8)) *
                        cos(radians(l.latitud::float8)) *
                        cos(radians(l.longitud::float8) - radians(%s::float8)) +
                        sin(radians(%s::float8)) *
                        sin(radians(l.latitud::float8))
                    ))
                )
            ) AS distancia_km
        FROM trabajo t
        INNER JOIN localizacion l ON l.id = t.localizacion_id
        WHERE t.id IN ({placeholders})
            AND t.localizacion_id IS NOT NULL
            AND l.latitud IS NOT NULL
            AND l.longitud IS NOT NULL
            {urgente_sql}
    )
    SELECT id
    FROM trabajos_con_localizacion
    WHERE distancia_km <= COALESCE(radio_busqueda_km::float8, %s::float8);
    """

    lat_u = float(latitud_usuario)
    lon_u = float(longitud_usuario)

    params = [
        lat_u,
        lon_u,
        lat_u,
        *trabajo_ids,
        float(rango),
    ]

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        return [row[0] for row in cursor.fetchall()]