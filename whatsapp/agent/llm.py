"""Cliente DeepSeek (API compatible con OpenAI) con loop de function-calling.

Import y configuración perezosos para no romper el arranque si falta el SDK o la
API key (mismo criterio que empresas/gemini_service.py).
"""
import json
import logging

from django.conf import settings
from decouple import UndefinedValueError, config

logger = logging.getLogger(__name__)

_client = None


def _mask(valor) -> str:
    texto = str(valor or '')
    if not texto:
        return '(vacío)'
    if len(texto) <= 12:
        return texto
    return f'{texto[:6]}…{texto[-4:]} ({len(texto)} chars)'


def _get_client():
    """Devuelve un cliente OpenAI apuntado a DeepSeek (cacheado)."""
    global _client
    if _client is not None:
        return _client
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError('El paquete openai no está instalado') from exc

    # Sin default: la key viene únicamente del entorno. Si falta, falla acá (al
    # usar el agente) y no al importar settings, que dejaba a Daphne sin levantar.
    try:
        api_key = config('DEEPSEEK_API_KEY')
    except UndefinedValueError as exc:
        logger.error("DEEPSEEK_API_KEY no está configurada en el entorno: el agente no puede responder")
        raise RuntimeError('DEEPSEEK_API_KEY no está configurada') from exc

    base_url = getattr(settings, 'DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
    logger.info(
        "DeepSeek client creado: base_url=%s | model=%s | api_key=%s",
        base_url, getattr(settings, 'DEEPSEEK_MODEL', 'deepseek-chat'), _mask(api_key),
    )
    _client = OpenAI(api_key=api_key, base_url=base_url)
    return _client


def run_conversation(system_prompt, mensajes, tool_specs, tool_dispatch, on_tool=None):
    """Corre una conversación con function-calling hasta obtener respuesta final.

    - system_prompt: str con las instrucciones de sistema.
    - mensajes: lista de dicts {'role', 'content'} (historial + turno actual).
    - tool_specs: lista de tool schemas en formato OpenAI (o [] para no usar tools).
    - tool_dispatch: callable(nombre, args_dict) -> dict/str con el resultado.
    - on_tool: callable(nombre, args, resultado) opcional para trazas.

    Devuelve el texto final del asistente (str).
    """
    client = _get_client()
    model = getattr(settings, 'DEEPSEEK_MODEL', 'deepseek-chat')
    max_rounds = getattr(settings, 'DEEPSEEK_MAX_TOOL_ROUNDS', 6)
    logger.info(
        "DeepSeek run_conversation: model=%s | mensajes=%s | tools=%s | max_rounds=%s",
        model, len(mensajes), len(tool_specs or []), max_rounds,
    )

    conversacion = [{'role': 'system', 'content': system_prompt}] + list(mensajes)
    kwargs_tools = {'tools': tool_specs, 'tool_choice': 'auto'} if tool_specs else {}

    for ronda in range(max_rounds):
        respuesta = client.chat.completions.create(
            model=model,
            messages=conversacion,
            temperature=0.3,
            **kwargs_tools,
        )
        mensaje = respuesta.choices[0].message
        tool_calls = getattr(mensaje, 'tool_calls', None)

        if not tool_calls:
            logger.info("DeepSeek respuesta final en ronda %s (len=%s)", ronda + 1, len(mensaje.content or ''))
            return (mensaje.content or '').strip()
        logger.info("DeepSeek ronda %s: %s tool_call(s)", ronda + 1, len(tool_calls))

        # Reinyectar el turno del asistente (con sus tool_calls) antes de responderlas.
        conversacion.append({
            'role': 'assistant',
            'content': mensaje.content or '',
            'tool_calls': [
                {
                    'id': tc.id,
                    'type': 'function',
                    'function': {'name': tc.function.name, 'arguments': tc.function.arguments},
                }
                for tc in tool_calls
            ],
        })

        for tc in tool_calls:
            nombre = tc.function.name
            try:
                args = json.loads(tc.function.arguments or '{}')
            except json.JSONDecodeError:
                args = {}
            try:
                resultado = tool_dispatch(nombre, args)
            except Exception as exc:  # noqa: BLE001 - queremos devolver el error al modelo
                logger.exception('Tool %s falló', nombre)
                resultado = {'error': f'La herramienta falló: {exc}'}
            if on_tool:
                try:
                    on_tool(nombre, args, resultado)
                except Exception:  # pragma: no cover
                    logger.exception('on_tool callback falló')
            conversacion.append({
                'role': 'tool',
                'tool_call_id': tc.id,
                'content': resultado if isinstance(resultado, str) else json.dumps(resultado, default=str, ensure_ascii=False),
            })

    # Se agotaron las rondas: pedir un cierre en texto sin más tools.
    respuesta = client.chat.completions.create(
        model=model,
        messages=conversacion + [{
            'role': 'system',
            'content': 'Cerrá la conversación con una respuesta útil en texto, sin llamar más herramientas.',
        }],
        temperature=0.3,
    )
    return (respuesta.choices[0].message.content or '').strip()
