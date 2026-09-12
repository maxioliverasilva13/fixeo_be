"""Geocodificación para el agente de WhatsApp (reusa Mapbox, igual que localizacion)."""
import logging
from urllib.parse import quote

import requests
from decouple import config

logger = logging.getLogger(__name__)


def geocode_texto(texto: str, pais: str = 'UY'):
    """Convierte una zona/ciudad en coordenadas.

    Usa Mapbox forward geocoding si hay MAPBOX_ACCESS_TOKEN; si no (o si Mapbox
    no devuelve resultados), cae a OpenStreetMap/Nominatim, que no requiere API
    key. Devuelve dict {lat, lon, ciudad, pais, place_name} o None si no se pudo.
    """
    texto = (texto or '').strip()
    if not texto:
        return None
    token = config('MAPBOX_ACCESS_TOKEN', default=None)
    if not token:
        return _geocode_nominatim(texto, pais)

    params = {
        'access_token': token,
        'limit': 1,
        'language': 'es',
        'autocomplete': 'false',
        'types': 'address,place,neighborhood,locality',
    }
    if pais:
        params['country'] = pais.upper()

    try:
        url = f"https://api.mapbox.com/geocoding/v5/mapbox.places/{quote(texto)}.json"
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        features = resp.json().get('features', [])
    except (requests.RequestException, ValueError):
        logger.exception('geocode_texto (mapbox) falló para %r', texto)
        return _geocode_nominatim(texto, pais)

    if not features:
        return _geocode_nominatim(texto, pais)

    feature = features[0]
    center = feature.get('center', [None, None])
    context = feature.get('context', [])
    ciudad = next((c['text'] for c in context if 'place' in c.get('id', '')), '')
    pais_nombre = next((c['text'] for c in context if 'country' in c.get('id', '')), '')
    return {
        'lon': center[0],
        'lat': center[1],
        'ciudad': ciudad or feature.get('text', ''),
        'pais': pais_nombre,
        'place_name': feature.get('place_name', ''),
    }


def _geocode_nominatim(texto: str, pais: str = 'UY'):
    """Fallback de geocodificación con OpenStreetMap/Nominatim (sin API key).

    Nominatim exige un User-Agent identificable y limita a ~1 req/seg; alcanza
    de sobra para el volumen del agente. Devuelve el mismo dict que Mapbox.

    Robustez: una dirección muy específica (ej. "Larrañaga 678 esquina Rincón,
    San José de Mayo, Uruguay") suele no matchear. Por eso se prueba la consulta
    completa y, si no hay resultado, se va soltando el componente más específico
    (separado por comas) hasta caer, como mínimo, en la ciudad.
    """
    variantes = _variantes_consulta(texto)
    for q in variantes:
        r = _nominatim_lookup(q, pais)
        if r:
            return r
    return None


def _variantes_consulta(texto: str, max_variantes: int = 8):
    """Genera consultas de más específica a más amplia.

    El usuario puede poner lo general (ciudad) al principio o al final, así que
    se prueban recortes desde AMBOS extremos:
    1) componentes por comas soltando desde la izquierda (se queda con la cola);
    2) idem soltando desde la derecha (se queda con la cabeza);
    3) cada componente por coma suelto;
    4) como último respaldo, recortes por palabras desde ambos extremos.
    Se deduplica preservando el orden y se acota la cantidad de intentos para no
    abusar del rate limit de Nominatim (~1 req/seg).
    """
    variantes = []

    partes = [p.strip() for p in (texto or '').split(',') if p.strip()]
    n = len(partes)
    for i in range(n):                       # colas: [i:]
        variantes.append(', '.join(partes[i:]))
    for j in range(n - 1, 0, -1):            # cabezas: [:j]
        variantes.append(', '.join(partes[:j]))
    variantes.extend(partes)                 # cada componente suelto

    palabras = (texto or '').replace(',', ' ').split()
    m = len(palabras)
    for i in range(1, m):                     # palabras desde la izquierda
        variantes.append(' '.join(palabras[i:]))
    for j in range(m - 1, 0, -1):             # palabras desde la derecha
        variantes.append(' '.join(palabras[:j]))

    vistas, unicas = set(), []
    for v in variantes:
        v = v.strip()
        if v and v.lower() not in vistas:
            vistas.add(v.lower())
            unicas.append(v)
    return unicas[:max_variantes]


def _nominatim_lookup(texto: str, pais: str = 'UY'):
    params = {
        'q': texto,
        'format': 'jsonv2',
        'limit': 1,
        'addressdetails': 1,
        'accept-language': 'es',
    }
    if pais:
        params['countrycodes'] = pais.lower()

    try:
        resp = requests.get(
            'https://nominatim.openstreetmap.org/search',
            params=params,
            headers={'User-Agent': 'Fixeo-WhatsApp-Agent/1.0 (soporte@fixeo.app)'},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json()
    except (requests.RequestException, ValueError):
        logger.exception('geocode_texto (nominatim) falló para %r', texto)
        return None

    if not results:
        return None

    r = results[0]
    addr = r.get('address', {})
    ciudad = addr.get('city') or addr.get('town') or addr.get('village') or addr.get('municipality') or ''
    try:
        lat, lon = float(r['lat']), float(r['lon'])
    except (KeyError, TypeError, ValueError):
        return None
    return {
        'lon': lon,
        'lat': lat,
        'ciudad': ciudad,
        'pais': addr.get('country', ''),
        'place_name': r.get('display_name', ''),
    }
