# utils.py o al inicio de tu views.py
from django.db import connection

def filtrar_trabajos_por_distancia_sql(trabajos_queryset, usuario, latitud_usuario, longitud_usuario, rango_km=None):
    """
    Filtra trabajos por distancia usando SQL directo.
    Retorna IDs de trabajos que están dentro del rango especificado.
    """
    if not latitud_usuario or not longitud_usuario:
        return []
    
    trabajo_ids = list(trabajos_queryset.values_list('id', flat=True))
    
    if not trabajo_ids:
        return []
    
    rango = rango_km or getattr(usuario, 'rango_mapa_km', 10) or 10
    
    placeholders = ','.join(['%s'] * len(trabajo_ids))
    
    query = f"""
    WITH trabajos_con_localizacion AS (
        SELECT 
            t.id,
            t.radio_busqueda_km,
            l.latitud,
            l.longitud,
            (
                6371 * acos(
                    cos(radians(%s)) * 
                    cos(radians(l.latitud)) * 
                    cos(radians(l.longitud) - radians(%s)) + 
                    sin(radians(%s)) * 
                    sin(radians(l.latitud))
                )
            ) AS distancia_km
        FROM trabajo t
        INNER JOIN localizacion l ON l.id = t.localizacion_id
        WHERE t.id IN ({placeholders})
            AND t.localizacion_id IS NOT NULL
            AND l.latitud IS NOT NULL 
            AND l.longitud IS NOT NULL
    )
    SELECT id
    FROM trabajos_con_localizacion
    WHERE distancia_km <= COALESCE(radio_busqueda_km, %s);
    """
    
    params = [
        float(latitud_usuario), 
        float(longitud_usuario), 
        float(latitud_usuario),
        *trabajo_ids,
        float(rango)
    ]
    
    with connection.cursor() as cursor:
        cursor.execute(query, params)
        return [row[0] for row in cursor.fetchall()]