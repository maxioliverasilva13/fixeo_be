"""Orquestador del agente: recibe un texto entrante y devuelve la respuesta."""
import logging

from django.utils import timezone

from . import tools
from .llm import run_conversation
from .prompts import SYSTEM_PROMPT, catalogo_profesiones, contexto_conversacion

logger = logging.getLogger(__name__)

MAX_HISTORIAL = 12  # turnos guardados (user+assistant) para contexto


def _system_prompt(conv):
    ahora = timezone.localtime().strftime('%Y-%m-%d %H:%M (%A)')
    catalogo = catalogo_profesiones()
    bloques = [SYSTEM_PROMPT, f"Fecha y hora actual: {ahora}."]
    if catalogo:
        bloques.append(catalogo)
    bloques.append(contexto_conversacion(conv))
    return "\n\n".join(bloques)


def _tool_specs(conv):
    """Sin ubicación no se ofrece `buscar`: fuerza el paso 1 (obtener ubicación)."""
    if conv.tiene_ubicacion:
        return tools.TOOL_SPECS
    return [t for t in tools.TOOL_SPECS if t['function']['name'] != 'buscar']


def responder_mensaje(conv, texto_usuario: str, trace=None) -> str:
    """Corre el agente para un mensaje entrante y devuelve la respuesta en texto.

    Persiste el historial en la conversación. Si el LLM no está configurado o
    falla, devuelve un fallback amable (no rompe el webhook).

    Si ``trace`` es una lista, se le agregan dicts {nombre, args, resultado} de
    cada tool-call (para inspección/debug; no afecta el flujo normal).
    """
    historial = list(conv.historial or [])
    mensajes = historial + [{'role': 'user', 'content': texto_usuario}]

    dispatch = tools.make_dispatch(conv)

    def on_tool(nombre, args, resultado):
        logger.info('WA tool %s(%s) -> %s', nombre, args, str(resultado)[:300])
        if trace is not None:
            trace.append({'nombre': nombre, 'args': args, 'resultado': resultado})

    try:
        respuesta = run_conversation(
            system_prompt=_system_prompt(conv),
            mensajes=mensajes,
            tool_specs=_tool_specs(conv),
            tool_dispatch=dispatch,
            on_tool=on_tool,
        )
    except Exception:
        logger.exception('Agente WhatsApp falló para wa_id=%s', conv.wa_id)
        return ('Perdón, tuve un problema para procesar tu mensaje. '
                '¿Podés repetirlo o intentar en un momento?')

    if not respuesta:
        respuesta = '¿En qué te puedo ayudar? Puedo buscar negocios o profesionales cerca tuyo.'

    nuevo_historial = mensajes + [{'role': 'assistant', 'content': respuesta}]
    conv.historial = nuevo_historial[-MAX_HISTORIAL:]
    conv.save(update_fields=['historial', 'ultima_actividad'])
    return respuesta
