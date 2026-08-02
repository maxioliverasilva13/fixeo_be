"""Filtro básico de contenido objetable (mensajes / texto UGC)."""

from __future__ import annotations

import re

# Lista mínima ES/EN; se puede ampliar sin cambiar API.
_BLOCKED_PATTERNS = [
    r'\bputa\b',
    r'\bputo\b',
    r'\bpelotudo\b',
    r'\bboludo\b',
    r'\bhij[oa]\s*de\s*puta\b',
    r'\bforro\b',
    r'\bnegro\s*de\s*mierda\b',
    r'\bfaggot\b',
    r'\bnigger\b',
    r'\bkill\s*yourself\b',
    r'\bkys\b',
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _BLOCKED_PATTERNS]


def contains_objectionable_content(text: str | None) -> bool:
    if not text or not str(text).strip():
        return False
    value = str(text)
    return any(rx.search(value) for rx in _COMPILED)


def filter_or_reject_message(text: str | None) -> str | None:
    """
    Devuelve mensaje de error si el texto no pasa el filtro; None si está OK.
    """
    if contains_objectionable_content(text):
        return (
            'Tu mensaje contiene lenguaje no permitido. '
            'ALaVuelta no tolera contenido ofensivo ni abusivo.'
        )
    return None
