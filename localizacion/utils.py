import math

import requests
from decouple import config


def reverse_geocode_country(lat, lng, timeout=6) -> str:
    """País (nombre, ej. 'Uruguay') detectado por reverse geocoding de Mapbox a
    partir de lat/lng. Devuelve '' si faltan coordenadas o falla la consulta."""
    if lat is None or lng is None:
        return ''
    try:
        mapbox_token = config('MAPBOX_ACCESS_TOKEN')
        url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{float(lng)},{float(lat)}.json"
        response = requests.get(
            url,
            params={'access_token': mapbox_token, 'types': 'country', 'language': 'es'},
            timeout=timeout,
        )
        response.raise_for_status()
        features = response.json().get('features', [])
        return features[0]['text'] if features else ''
    except Exception:
        return ''


def calcular_distancia_km(lat1, lon1, lat2, lon2):
    R = 6371

    lat1, lon1, lat2, lon2 = map(
        float,
        [lat1, lon1, lat2, lon2]
    )

    lat1, lon1, lat2, lon2 = map(
        math.radians,
        [lat1, lon1, lat2, lon2]
    )

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return round(R * c, 2)