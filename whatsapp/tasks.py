import logging

from celery import shared_task

from usuario.models import Usuario
from . import services

logger = logging.getLogger(__name__)


@shared_task
def enviar_mensaje_whatsapp_task(usuario_id, body, profesional_id=None):
    logger.info("enviar_mensaje_whatsapp_task: iniciado para usuario_id=%s", usuario_id)

    if profesional_id is not None:
        from suscripciones.utils import usuario_tiene_plan_pago
        profesional = Usuario.objects.filter(id=profesional_id).first()
        if not usuario_tiene_plan_pago(profesional):
            logger.info(
                "enviar_mensaje_whatsapp_task: omitido, profesional %s no tiene plan pago",
                profesional_id,
            )
            return

    try:
        usuario = Usuario.objects.get(id=usuario_id)
    except Usuario.DoesNotExist:
        logger.warning("enviar_mensaje_whatsapp_task: usuario %s no existe", usuario_id)
        return

    if not usuario.telefono:
        logger.info("enviar_mensaje_whatsapp_task: usuario %s no tiene telefono cargado", usuario_id)
        return

    telefono = services.normalizar_numero_whatsapp(usuario.telefono)
    logger.info(
        "enviar_mensaje_whatsapp_task: enviando a telefono=%s (crudo=%s, usuario_id=%s)",
        telefono, usuario.telefono, usuario_id,
    )
    mensaje = services.enviar_mensaje_texto(telefono, body, usuario=usuario)
    logger.info(
        "enviar_mensaje_whatsapp_task: resultado estado=%s (usuario_id=%s, wa_message_id=%s)",
        mensaje.estado, usuario_id, mensaje.wa_message_id,
    )
