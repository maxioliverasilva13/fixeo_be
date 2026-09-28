"""Premio para el profesional que invitó a alguien que se registró con su link."""

import logging
from datetime import timedelta

from django.utils import timezone

from ..models import Subscripcion

logger = logging.getLogger(__name__)

DIAS_EXTRA_REFERIDO = 5


def otorgar_premio_invitacion(invitador) -> None:
    """
    Al invitador se le suman DIAS_EXTRA_REFERIDO días a su suscripción activa
    (sea plan gratis o pago). Sin suscripción activa: no-op (caso borde, se loguea).
    """
    subscripcion = (
        Subscripcion.objects
        .filter(user_id=invitador, cancelada=False, expiracion__gt=timezone.now())
        .order_by('-created_at')
        .first()
    )

    if not subscripcion:
        logger.warning('otorgar_premio_invitacion: invitador=%s sin suscripción activa', invitador.pk)
        return

    subscripcion.expiracion = subscripcion.expiracion + timedelta(days=DIAS_EXTRA_REFERIDO)
    subscripcion.save(update_fields=['expiracion'])


def beneficio_texto(invitador) -> str:
    """Texto a mostrar en la pantalla de "invitar amigos"."""
    return f"Invitá a un amigo y ganá {DIAS_EXTRA_REFERIDO} días gratis en tu plan actual"
