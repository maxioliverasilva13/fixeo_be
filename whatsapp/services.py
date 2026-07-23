import logging
import re

import requests
from django.conf import settings

from usuario.models import Usuario
from .models import WhatsAppMessage

logger = logging.getLogger(__name__)


def normalizar_numero_whatsapp(telefono: str) -> str:
    """
    Usuario.telefono se guarda sin código de país. La API de Meta necesita el
    número completo (código de país + número, sin '+'), así que si el número
    es corto le antepone WHATSAPP_DEFAULT_COUNTRY_CODE.
    """
    numero = re.sub(r'\D', '', telefono or '')
    if numero and len(numero) <= 9:
        numero = f"{settings.WHATSAPP_DEFAULT_COUNTRY_CODE}{numero}"
    return numero


class MetaWhatsAppClient:
    """Cliente para enviar mensajes salientes vía la API de WhatsApp Cloud (Meta)."""

    def __init__(self):
        self.base_url = settings.WHATSAPP_GRAPH_BASE_URL.rstrip('/')
        self.api_version = settings.WHATSAPP_API_VERSION
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self.access_token = settings.WHATSAPP_ACCESS_TOKEN

    def _headers(self):
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
        }

    def _post(self, payload: dict) -> dict:
        url = f"{self.base_url}/{self.api_version}/{self.phone_number_id}/messages"
        logger.info(
            "Meta WhatsApp API request: url=%s to=%r (len=%s)",
            url, payload.get('to'), len(payload.get('to') or ''),
        )
        response = requests.post(url, json=payload, headers=self._headers(), timeout=15)
        if not response.ok:
            logger.error(
                "Meta WhatsApp API respondió %s: %s",
                response.status_code, response.text,
            )
        response.raise_for_status()
        return response.json()

    def enviar_mensaje_texto(self, to: str, body: str) -> dict:
        payload = {
            'messaging_product': 'whatsapp',
            'to': to,
            'type': 'text',
            'text': {'body': body},
        }
        return self._post(payload)

    def enviar_template(self, to: str, template_name: str, language_code: str = 'es', components: list = None) -> dict:
        payload = {
            'messaging_product': 'whatsapp',
            'to': to,
            'type': 'template',
            'template': {
                'name': template_name,
                'language': {'code': language_code},
                'components': components or [],
            },
        }
        return self._post(payload)


def enviar_mensaje_texto(to: str, body: str, usuario: Usuario = None) -> WhatsAppMessage:
    logger.info("enviar_mensaje_texto: preparando envío a %s (usuario_id=%s)", to, getattr(usuario, 'id', None))
    client = MetaWhatsAppClient()
    mensaje = WhatsAppMessage.objects.create(
        wa_id=to,
        usuario=usuario,
        direccion=WhatsAppMessage.DIRECCION_SALIENTE,
        tipo='text',
        texto=body,
        estado=WhatsAppMessage.ESTADO_PENDIENTE,
    )
    try:
        respuesta = client.enviar_mensaje_texto(to, body)
        mensaje.wa_message_id = respuesta.get('messages', [{}])[0].get('id')
        mensaje.estado = WhatsAppMessage.ESTADO_ENVIADO
        mensaje.payload = respuesta
        logger.info("enviar_mensaje_texto: enviado OK a %s (wa_message_id=%s)", to, mensaje.wa_message_id)
    except requests.RequestException as exc:
        logger.exception("Error enviando mensaje de WhatsApp a %s", to)
        mensaje.estado = WhatsAppMessage.ESTADO_FALLIDO
        response = getattr(exc, 'response', None)
        if response is not None:
            try:
                mensaje.payload = response.json()
            except ValueError:
                mensaje.payload = {'error': response.text}
    mensaje.save(update_fields=['wa_message_id', 'estado', 'payload', 'updated_at'])
    return mensaje


def _buscar_usuario_por_telefono(wa_id: str):
    return Usuario.objects.filter(telefono__endswith=wa_id[-8:]).first() if wa_id else None


def _procesar_mensajes_entrantes(value: dict):
    for mensaje in value.get('messages', []):
        wa_id = mensaje.get('from')
        tipo = mensaje.get('type', 'text')
        texto = mensaje.get('text', {}).get('body') if tipo == 'text' else None

        WhatsAppMessage.objects.update_or_create(
            wa_message_id=mensaje.get('id'),
            defaults={
                'wa_id': wa_id,
                'usuario': _buscar_usuario_por_telefono(wa_id),
                'direccion': WhatsAppMessage.DIRECCION_ENTRANTE,
                'tipo': tipo,
                'estado': WhatsAppMessage.ESTADO_RECIBIDO,
                'texto': texto,
                'payload': mensaje,
            },
        )

        try:
            enviar_mensaje_texto(wa_id, 'Hola! 👋')
        except Exception:
            logger.exception("Error mandando auto-respuesta a %s", wa_id)


def _procesar_estados(value: dict):
    estado_map = {
        'sent': WhatsAppMessage.ESTADO_ENVIADO,
        'delivered': WhatsAppMessage.ESTADO_ENTREGADO,
        'read': WhatsAppMessage.ESTADO_LEIDO,
        'failed': WhatsAppMessage.ESTADO_FALLIDO,
    }
    for status_update in value.get('statuses', []):
        nuevo_estado = estado_map.get(status_update.get('status'))
        if not nuevo_estado:
            continue
        WhatsAppMessage.objects.filter(
            wa_message_id=status_update.get('id'),
        ).update(estado=nuevo_estado)


def procesar_webhook_payload(data: dict):
    """Procesa el payload entrante de un webhook de WhatsApp Cloud API (Meta)."""
    for entry in data.get('entry', []):
        for change in entry.get('changes', []):
            value = change.get('value', {})
            _procesar_estados(value)
