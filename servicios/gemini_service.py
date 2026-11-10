"""Generación de servicios básicos con Google Gemini (texto → JSON).

No crea nada en la base: solo sugiere. El admin revisa/edita y confirma el alta
desde el frontend.
"""
import json
import logging
import re
import uuid
from decimal import Decimal, InvalidOperation

from django.conf import settings

logger = logging.getLogger(__name__)

_configured = False

# Mismo fallback que profesiones sin ícono propio.
_DEFAULT_SERVICIO_FOTO = (
    'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/'
    'bucketFixea/iconsProfesiones/box-open.png'
)


def _get_genai():
    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise RuntimeError('El paquete google-generativeai no está instalado') from exc
    return genai


def _ensure_configured():
    global _configured
    genai = _get_genai()
    if _configured:
        return genai
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        raise RuntimeError('GEMINI_API_KEY no está configurada')
    genai.configure(api_key=api_key)
    _configured = True
    return genai


def _normalizar_precio(valor):
    if valor is None:
        return None
    texto = str(valor).strip()
    if not texto:
        return None
    limpio = (
        texto.replace('$', '')
        .replace('USD', '')
        .replace('ARS', '')
        .replace('UYU', '')
        .replace(' ', '')
        .strip()
    )
    if ',' in limpio and '.' in limpio:
        limpio = limpio.replace('.', '').replace(',', '.')
    elif ',' in limpio:
        limpio = limpio.replace(',', '.')
    try:
        n = Decimal(limpio)
    except (InvalidOperation, ValueError):
        return None
    if n <= 0:
        return None
    return str(n)


def _normalizar_tiempo(valor):
    if valor is None:
        return 60
    try:
        n = int(float(str(valor).strip()))
    except (TypeError, ValueError):
        return 60
    return max(15, min(n, 8 * 60))


def _pollinations_url(query: str) -> str:
    from urllib.parse import quote

    q = re.sub(r'\s+', ' ', (query or '').strip())[:140]
    if not q:
        return ''
    # seed distinto por query para no repetir la misma imagen en todos.
    seed = abs(hash(q)) % 10_000
    return (
        f'https://image.pollinations.ai/prompt/{quote(q)}'
        f'?width=640&height=480&nologo=true&seed={seed}'
    )


def _subir_bytes_supabase(content: bytes, content_type: str = 'image/jpeg') -> str:
    """Sube bytes a Supabase y devuelve URL pública. '' si no se puede."""
    import requests
    from decouple import config

    supabase_url = (config('SUPABASE_URL', default='') or '').rstrip('/')
    supabase_key = config('SUPABASE_KEY', default='') or ''
    supabase_bucket = config('SUPABASE_BUCKET', default='fixeo-uploads')
    if not supabase_url or not supabase_key or not content:
        return ''

    ext = '.jpg'
    if 'png' in (content_type or ''):
        ext = '.png'
    elif 'webp' in (content_type or ''):
        ext = '.webp'
    file_path = f"uploads/servicios-ia/{uuid.uuid4()}{ext}"
    upload_url = f"{supabase_url}/storage/v1/object/{supabase_bucket}/{file_path}"
    headers = {
        'Authorization': f'Bearer {supabase_key}',
        'Content-Type': content_type or 'image/jpeg',
        'x-upsert': 'false',
    }
    response = requests.post(upload_url, data=content, headers=headers, timeout=30)
    if response.status_code not in (200, 201):
        logger.warning('Supabase upload falló (%s): %s', response.status_code, response.text[:200])
        return ''
    return f"{supabase_url}/storage/v1/object/public/{supabase_bucket}/{file_path}"


def _materializar_foto(query: str, fallback: str = '') -> str:
    """Imagen acorde al servicio en Supabase; si falla, logo/profesión o default fijo."""
    import requests

    fallback = (fallback or '').strip() or _DEFAULT_SERVICIO_FOTO
    source = _pollinations_url(query)
    if not source:
        return fallback

    try:
        # Timeout corto: si Pollinations no responde, caemos al default de la profesión.
        resp = requests.get(source, timeout=8)
        if resp.status_code != 200 or not resp.content or len(resp.content) < 500:
            logger.info('Pollinations sin imagen usable (%s)', resp.status_code)
            return fallback
        content_type = (resp.headers.get('Content-Type') or 'image/jpeg').split(';')[0].strip()
        if not content_type.startswith('image/'):
            return fallback
        uploaded = _subir_bytes_supabase(resp.content, content_type)
        return uploaded or fallback
    except Exception as exc:
        logger.warning('No se pudo materializar foto de servicio IA: %s', exc)
        return fallback


def _construir_prompt(profesion_nombre, prompt_usuario, divisa, cantidad_sugerida=6):
    return f"""Sos un asistente para armar el catálogo de servicios de un profesional en Fixeo (LatAm).

Profesión: {profesion_nombre}
Moneda de referencia: {divisa}
Cantidad deseada: aproximadamente {cantidad_sugerida} servicios.

Instrucciones del administrador (seguilas con prioridad):
\"\"\"{prompt_usuario}\"\"\"

Para cada servicio devolvé un objeto con:
- "nombre": título corto y claro (obligatorio).
- "descripcion": 1–2 oraciones útiles para el cliente (puede ser "").
- "precio": número como string si es precio fijo (ej: "1500.00"). "" si usás rango.
- "precio_min": número como string si es precio a convenir/rango. "" si es fijo.
- "precio_max": número como string si es rango. "" si es fijo.
- "tiempo_minutos": duración estimada en minutos (entero, tip. 30–180).
- "imagen_descripcion": frase CORTA en inglés (máx. 12 palabras) que describa una foto
  simple y representativa del servicio (ej: "house exterior wall painting brush ladder").
  Sin marcas, sin texto en la imagen, estilo foto realista simple.

Reglas:
- Usá precios realistas de mercado para {profesion_nombre} en LatAm, en {divisa}.
- Cada servicio tiene precio FIJO (solo "precio") O rango (precio_min + precio_max), nunca ambos.
- En rango, precio_max >= precio_min > 0.
- No dupliques nombres.
- No inventes URLs de fotos: solo "imagen_descripcion".
- Respondé EXCLUSIVAMENTE un JSON válido con esta forma, sin markdown ni texto extra:
  {{"servicios":[{{"nombre":"...","descripcion":"...","precio":"...","precio_min":"","precio_max":"","tiempo_minutos":60,"imagen_descripcion":"..."}}]}}
"""


def _extraer_json(raw: str):
    texto = (raw or '').strip()
    if not texto:
        return None
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass
    match = re.search(r'\{[\s\S]*\}', texto)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def generar_servicios_basicos(
    *,
    profesion_nombre: str,
    prompt: str,
    divisa: str = 'UYU',
    foto_default: str = '',
    cantidad: int = 6,
):
    """Devuelve lista de dicts listos para precargar un bulk-create.

    Cada item: nombre, descripcion, precio, precio_min, precio_max,
    tiempo_minutos, divisa, foto.
    """
    genai = _ensure_configured()
    profesion_nombre = (profesion_nombre or '').strip() or 'Servicios generales'
    prompt = (prompt or '').strip()
    if not prompt:
        raise ValueError('El prompt es obligatorio')

    cantidad = max(3, min(int(cantidad or 6), 12))
    divisa = (divisa or 'UYU').strip().upper()[:3]
    foto_default = (foto_default or '').strip()

    model = genai.GenerativeModel(
        model_name=getattr(settings, 'GEMINI_MODEL', 'gemini-2.5-flash'),
        generation_config={
            'response_mime_type': 'application/json',
            'temperature': 0.4,
        },
    )

    response = model.generate_content(
        _construir_prompt(profesion_nombre, prompt, divisa, cantidad)
    )
    raw = (getattr(response, 'text', '') or '').strip()
    data = _extraer_json(raw)
    if data is None:
        logger.error('Respuesta de Gemini no es JSON válido: %s', raw[:500])
        raise ValueError('La respuesta de la IA no es un JSON válido')

    items_raw = data.get('servicios', []) if isinstance(data, dict) else []
    if not isinstance(items_raw, list):
        return []

    servicios = []
    seen = set()
    for item in items_raw:
        if not isinstance(item, dict):
            continue
        nombre = str(item.get('nombre', '')).strip()
        if not nombre:
            continue
        key = nombre.lower()
        if key in seen:
            continue
        seen.add(key)

        precio = _normalizar_precio(item.get('precio'))
        precio_min = _normalizar_precio(item.get('precio_min'))
        precio_max = _normalizar_precio(item.get('precio_max'))

        # Preferir rango si ambos extremos son válidos; si no, precio fijo.
        if precio_min and precio_max:
            try:
                if Decimal(precio_max) < Decimal(precio_min):
                    precio_min, precio_max = precio_max, precio_min
            except InvalidOperation:
                precio_min = precio_max = None
            precio = None
        elif precio:
            precio_min = None
            precio_max = None
        else:
            # Sin precio usable: saltar
            continue

        imagen_desc = str(
            item.get('imagen_descripcion')
            or item.get('image_description')
            or item.get('foto_query')
            or ''
        ).strip()
        if not imagen_desc:
            imagen_desc = f'{profesion_nombre} {nombre} realistic service photo'
        foto = _materializar_foto(imagen_desc, fallback=foto_default)

        servicios.append({
            'nombre': nombre[:200],
            'descripcion': str(item.get('descripcion', '') or '').strip()[:1000],
            'precio': precio or '',
            'precio_min': precio_min or '',
            'precio_max': precio_max or '',
            'tiempo_minutos': _normalizar_tiempo(item.get('tiempo_minutos')),
            'divisa': divisa,
            'foto': foto,
        })

    return servicios
