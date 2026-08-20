"""Servicio de análisis de imágenes de productos con Google Gemini.

Recibe una imagen (bytes) y devuelve una lista de productos detectados, ya
normalizados con los campos que necesita el alta de producto. NO crea nada en
la base de datos: solo detecta. La creación la confirma el usuario desde el
frontend tras revisar/editar los resultados.
"""
import json
import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings

logger = logging.getLogger(__name__)

_configured = False


def _get_genai():
    """Import perezoso del SDK para no romper el arranque si no está instalado."""
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


def _construir_prompt(categorias_existentes):
    categorias_str = ', '.join(categorias_existentes) if categorias_existentes else '(no hay categorías)'
    return f"""Analizá esta imagen e identificá TODOS los productos vendibles que aparecen.

Para cada producto devolvé un objeto con estos campos:
- "nombre": nombre corto y claro del producto (OBLIGATORIO).
- "descripcion": descripción breve del producto. "" si no aplica.
- "precio": el precio SOLO si es claramente visible en la imagen (etiqueta o cartel),
  como número sin símbolo de moneda ni separador de miles (ej: "1500.00"). Si no es
  visible, devolvé "" (string vacío). NO inventes precios.
- "codigo": código/SKU/código de barras SOLO si es visible en la imagen. "" si no.
- "categoria_sugerida": elegí la categoría MÁS adecuada de esta lista existente:
  [{categorias_str}]. Copiá el nombre EXACTAMENTE como aparece en la lista.
  Si ninguna encaja o no hay lista, devolvé "".

Reglas importantes:
- No inventes precios ni códigos que no estén visibles en la imagen.
- Si hay varias unidades del mismo producto, devolvelo UNA sola vez.
- Ignorá objetos que no sean productos vendibles (personas, mobiliario, fondo, etc.).
- Respondé EXCLUSIVAMENTE un JSON válido con esta forma exacta, sin texto adicional:
  {{"productos": [{{"nombre": "...", "descripcion": "...", "precio": "...", "codigo": "...", "categoria_sugerida": "..."}}]}}
"""


def _normalizar_precio(valor):
    """Devuelve un precio como string ('' si no es válido/visible)."""
    if valor is None:
        return ''
    texto = str(valor).strip()
    if not texto:
        return ''
    # Quitar símbolos de moneda y separadores de miles comunes
    limpio = (
        texto.replace('$', '')
        .replace('USD', '')
        .replace('ARS', '')
        .replace('UYU', '')
        .replace(' ', '')
        .strip()
    )
    # Si viene con coma decimal (1.500,00 -> 1500.00)
    if ',' in limpio and '.' in limpio:
        limpio = limpio.replace('.', '').replace(',', '.')
    elif ',' in limpio:
        limpio = limpio.replace(',', '.')
    try:
        return str(Decimal(limpio))
    except (InvalidOperation, ValueError):
        return ''


def _matchear_categoria(sugerida, categorias_existentes):
    """Devuelve el nombre exacto de la categoría existente que matchea, o ''."""
    if not sugerida:
        return ''
    sugerida_lower = sugerida.strip().lower()
    for cat in categorias_existentes:
        if cat.strip().lower() == sugerida_lower:
            return cat
    return ''


def analizar_imagen_productos(image_bytes, mime_type, categorias_existentes=None, divisa_default='USD'):
    """Analiza una imagen y devuelve una lista de productos detectados.

    Cada producto es un dict: {nombre, descripcion, precio, codigo,
    categoria_sugerida, divisa}. Lanza RuntimeError si Gemini no está
    configurado; cualquier otra excepción (red, parseo) se propaga.
    """
    genai = _ensure_configured()
    categorias_existentes = list(categorias_existentes or [])

    model = genai.GenerativeModel(
        model_name=getattr(settings, 'GEMINI_MODEL', 'gemini-2.0-flash'),
        generation_config={
            'response_mime_type': 'application/json',
            'temperature': 0.2,
        },
    )

    response = model.generate_content([
        {'mime_type': mime_type, 'data': image_bytes},
        _construir_prompt(categorias_existentes),
    ])

    raw = (getattr(response, 'text', '') or '').strip()
    if not raw:
        logger.warning('Gemini devolvió una respuesta vacía')
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.error('Respuesta de Gemini no es JSON válido: %s', raw[:500])
        raise ValueError('La respuesta de la IA no es un JSON válido')

    productos_raw = data.get('productos', []) if isinstance(data, dict) else []
    if not isinstance(productos_raw, list):
        return []

    productos = []
    for item in productos_raw:
        if not isinstance(item, dict):
            continue
        nombre = str(item.get('nombre', '')).strip()
        if not nombre:
            continue
        productos.append({
            'nombre': nombre[:200],
            'descripcion': str(item.get('descripcion', '') or '').strip(),
            'precio': _normalizar_precio(item.get('precio')),
            'codigo': str(item.get('codigo', '') or '').strip()[:100],
            'categoria_sugerida': _matchear_categoria(
                str(item.get('categoria_sugerida', '') or ''), categorias_existentes
            ),
            'divisa': divisa_default,
        })

    return productos
