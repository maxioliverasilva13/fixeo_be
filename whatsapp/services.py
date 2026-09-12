import logging
import re

import requests
from django.conf import settings

from decimal import Decimal

from usuario.models import Usuario
from .models import ConversacionWhatsApp, WhatsAppMessage

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


class WhatsAppClient:
    """Cliente para enviar mensajes salientes por WhatsApp.

    Soporta dos proveedores según ``settings.WHATSAPP_PROVIDER``:
    - ``'360dialog'``: Cloud API hosteada por 360dialog. POST a
      ``{base}/messages`` con header ``D360-API-KEY``. No lleva phone_number_id
      ni versión en la ruta.
    - ``'meta'``: Graph API directa de Meta. POST a
      ``{base}/{version}/{phone_number_id}/messages`` con ``Authorization: Bearer``.

    El body del mensaje (messaging_product/to/type/…) es idéntico en ambos.
    """

    def __init__(self):
        self.provider = (settings.WHATSAPP_PROVIDER or 'meta').lower()
        if self.provider == '360dialog':
            self.base_url = settings.WHATSAPP_360_BASE_URL.rstrip('/')
            self.api_key = settings.WHATSAPP_360_API_KEY
            self.messages_url = f"{self.base_url}/messages"
        else:
            self.base_url = settings.WHATSAPP_GRAPH_BASE_URL.rstrip('/')
            self.api_version = settings.WHATSAPP_API_VERSION
            self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
            self.access_token = settings.WHATSAPP_ACCESS_TOKEN
            self.messages_url = f"{self.base_url}/{self.api_version}/{self.phone_number_id}/messages"

    def _headers(self):
        if self.provider == '360dialog':
            return {
                'D360-API-KEY': self.api_key,
                'Content-Type': 'application/json',
            }
        return {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
        }

    def _post(self, payload: dict) -> dict:
        url = self.messages_url
        logger.info(
            "WhatsApp API request [%s]: url=%s to=%r (len=%s)",
            self.provider, url, payload.get('to'), len(payload.get('to') or ''),
        )
        response = requests.post(url, json=payload, headers=self._headers(), timeout=15)
        if not response.ok:
            logger.error(
                "WhatsApp API [%s] respondió %s: %s",
                self.provider, response.status_code, response.text,
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


# Alias de compatibilidad: el cliente antes se llamaba MetaWhatsAppClient.
MetaWhatsAppClient = WhatsAppClient


def enviar_mensaje_texto(to: str, body: str, usuario: Usuario = None) -> WhatsAppMessage:
    logger.info("enviar_mensaje_texto: preparando envío a %s (usuario_id=%s)", to, getattr(usuario, 'id', None))
    client = WhatsAppClient()
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


def enviar_template_mensaje(to: str, template_name: str, components: list = None,
                           language_code: str = None, usuario: Usuario = None) -> WhatsAppMessage:
    """Envía un template de WhatsApp (mensaje proactivo fuera de la ventana de 24 h).

    Espejo de ``enviar_mensaje_texto``: persiste un ``WhatsAppMessage`` (tipo
    ``template``) y registra estado/payload de la respuesta o el error.
    """
    language_code = language_code or getattr(settings, 'WHATSAPP_TEMPLATE_LANG', 'es')
    logger.info(
        "enviar_template_mensaje: preparando template %r a %s (usuario_id=%s)",
        template_name, to, getattr(usuario, 'id', None),
    )
    client = WhatsAppClient()
    mensaje = WhatsAppMessage.objects.create(
        wa_id=to,
        usuario=usuario,
        direccion=WhatsAppMessage.DIRECCION_SALIENTE,
        tipo='template',
        texto=template_name,
        estado=WhatsAppMessage.ESTADO_PENDIENTE,
    )
    try:
        respuesta = client.enviar_template(to, template_name, language_code=language_code, components=components)
        mensaje.wa_message_id = respuesta.get('messages', [{}])[0].get('id')
        mensaje.estado = WhatsAppMessage.ESTADO_ENVIADO
        mensaje.payload = respuesta
        logger.info("enviar_template_mensaje: enviado OK a %s (wa_message_id=%s)", to, mensaje.wa_message_id)
    except requests.RequestException as exc:
        logger.exception("Error enviando template %r de WhatsApp a %s", template_name, to)
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


def _es_profesional(usuario) -> bool:
    return bool(usuario) and not usuario.is_owner_empresa and usuario.usuario_profesiones.exists()


def _agente_habilitado(conv) -> bool:
    if not getattr(settings, 'WHATSAPP_AGENTE_ACTIVO', True):
        return False
    usuario = conv.usuario
    if _es_profesional(usuario):
        return usuario.activar_agente
    return True


def obtener_o_crear_conversacion(wa_id: str) -> ConversacionWhatsApp:
    """Devuelve la conversación del número, creándola y asociando usuario si existe."""
    conv, creada = ConversacionWhatsApp.objects.get_or_create(wa_id=wa_id)
    if not conv.usuario_id:
        usuario = _buscar_usuario_por_telefono(wa_id)
        if usuario:
            conv.usuario = usuario
            conv.save(update_fields=['usuario', 'ultima_actividad'])
    return conv


def _texto_desde_mensaje(mensaje: dict, tipo: str):
    """Extrae el texto relevante según el tipo de mensaje de WhatsApp."""
    if tipo == 'text':
        return mensaje.get('text', {}).get('body')
    if tipo == 'interactive':
        interactive = mensaje.get('interactive', {})
        if interactive.get('type') == 'button_reply':
            return interactive.get('button_reply', {}).get('title')
        if interactive.get('type') == 'list_reply':
            return interactive.get('list_reply', {}).get('title')
    if tipo == 'button':
        return mensaje.get('button', {}).get('text')
    return None


def _guardar_ubicacion_de_mensaje(conv: ConversacionWhatsApp, mensaje: dict) -> bool:
    """Si el mensaje trae una ubicación nativa de WhatsApp, la persiste. Devuelve True si lo hizo."""
    loc = mensaje.get('location') or {}
    lat, lon = loc.get('latitude'), loc.get('longitude')
    if lat is None or lon is None:
        return False
    conv.ubicacion_lat = Decimal(str(lat))
    conv.ubicacion_lon = Decimal(str(lon))
    if loc.get('name'):
        conv.ciudad = str(loc.get('name'))[:120]
    if conv.estado == ConversacionWhatsApp.ESTADO_ESPERANDO_UBICACION:
        conv.estado = ConversacionWhatsApp.ESTADO_IDLE
    conv.save(update_fields=['ubicacion_lat', 'ubicacion_lon', 'ciudad', 'estado', 'ultima_actividad'])
    return True


def _procesar_mensajes_entrantes(value: dict):
    from .tasks import procesar_mensaje_entrante_task

    for mensaje in value.get('messages', []):
        wa_id = mensaje.get('from')
        if not wa_id:
            continue
        tipo = mensaje.get('type', 'text')
        texto = _texto_desde_mensaje(mensaje, tipo)

        # Dedupe por wa_message_id (unique). Si ya existía, no reprocesar.
        _, creado = WhatsAppMessage.objects.get_or_create(
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
        if not creado:
            logger.info("Mensaje %s ya procesado, se omite", mensaje.get('id'))
            continue

        conv = obtener_o_crear_conversacion(wa_id)
        trae_ubicacion = _guardar_ubicacion_de_mensaje(conv, mensaje)

        if not _agente_habilitado(conv):
            continue

        if texto is None and trae_ubicacion:
            texto = 'Te comparto mi ubicación.'
        if texto is None:
            # Tipos no soportados (audio/imagen/etc.): respuesta rápida guía.
            try:
                enviar_mensaje_texto(wa_id, 'Por ahora solo puedo leer mensajes de texto y ubicación. '
                                            'Contame qué negocio o servicio buscás. 🙂', usuario=conv.usuario)
            except Exception:
                logger.exception("Error respondiendo tipo no soportado a %s", wa_id)
            continue

        try:
            procesar_mensaje_entrante_task.delay(conv.id, texto)
        except Exception:
            logger.exception("No se pudo encolar el agente; procesando en línea para %s", wa_id)
            procesar_mensaje_entrante_task(conv.id, texto)


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
            _procesar_mensajes_entrantes(value)
