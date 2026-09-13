"""Diagnóstico del canal de WhatsApp de punta a punta.

Pensado para correr en el server (Railway) y ver en un solo lugar por qué un
mensaje no sale o el agente no responde. No modifica nada salvo con --enviar.

Uso:
    python manage.py wa_diagnostico
    python manage.py wa_diagnostico --enviar 59891664536
    python manage.py wa_diagnostico --agente 59891664536 --texto "Hola"
    python manage.py wa_diagnostico --webhook
"""
import os

import requests
from django.conf import settings
from django.core.management.base import BaseCommand


def _mask(valor) -> str:
    texto = str(valor or '')
    if not texto:
        return '(vacío)'
    if len(texto) <= 12:
        return texto
    return f'{texto[:6]}…{texto[-4:]} ({len(texto)} chars)'


class Command(BaseCommand):
    help = "Muestra la configuración efectiva de WhatsApp y prueba envío/agente opcionalmente."

    def add_arguments(self, parser):
        parser.add_argument('--enviar', metavar='NUMERO', help='Envía un mensaje de prueba a ese número.')
        parser.add_argument('--texto', default='Prueba de diagnóstico desde fixeo_be 👋')
        parser.add_argument('--agente', metavar='WA_ID', help='Corre el agente (sin Celery) para ese wa_id.')
        parser.add_argument('--webhook', action='store_true', help='Consulta el webhook registrado en 360dialog.')
        parser.add_argument('--ultimos', type=int, default=6, help='Cuántos mensajes recientes mostrar.')
        parser.add_argument('--api-key', help='Prueba con esta D360-API-KEY en vez de la configurada.')
        parser.add_argument('--provider', help='Prueba con este proveedor (360dialog|meta) en vez del configurado.')

    def handle(self, *args, **opts):
        w = self.stdout.write
        if opts.get('provider'):
            settings.WHATSAPP_PROVIDER = opts['provider']
            w(self.style.WARNING(f'  (override) WHATSAPP_PROVIDER={opts["provider"]}'))
        if opts.get('api_key'):
            settings.WHATSAPP_360_API_KEY = opts['api_key']
            w(self.style.WARNING(f'  (override) WHATSAPP_360_API_KEY={_mask(opts["api_key"])}'))
        provider = (getattr(settings, 'WHATSAPP_PROVIDER', '') or 'meta').lower()

        w(self.style.MIGRATE_HEADING('Configuración efectiva'))
        w(f'  WHATSAPP_PROVIDER          = {provider}')
        w(f'  WHATSAPP_360_BASE_URL      = {getattr(settings, "WHATSAPP_360_BASE_URL", "")}')
        w(f'  WHATSAPP_360_API_KEY       = {_mask(getattr(settings, "WHATSAPP_360_API_KEY", ""))}')
        w(f'  WHATSAPP_ACCESS_TOKEN      = {_mask(getattr(settings, "WHATSAPP_ACCESS_TOKEN", ""))}')
        w(f'  WHATSAPP_PHONE_NUMBER_ID   = {getattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "") or "(vacío)"}')
        w(f'  WHATSAPP_API_VERSION       = {getattr(settings, "WHATSAPP_API_VERSION", "")}')
        w(f'  WHATSAPP_GRAPH_BASE_URL    = {getattr(settings, "WHATSAPP_GRAPH_BASE_URL", "")}')
        w(f'  WHATSAPP_APP_SECRET        = {"configurado" if getattr(settings, "WHATSAPP_APP_SECRET", "") else "(vacío)"}')
        w(f'  WHATSAPP_WEBHOOK_URL_TOKEN = {"configurado" if getattr(settings, "WHATSAPP_WEBHOOK_URL_TOKEN", "") else "(vacío)"}')
        w(f'  WHATSAPP_AGENTE_ACTIVO     = {getattr(settings, "WHATSAPP_AGENTE_ACTIVO", None)}')
        w(f'  WHATSAPP_DEFAULT_CC        = {getattr(settings, "WHATSAPP_DEFAULT_COUNTRY_CODE", "")}')
        w(f'  DEEPSEEK_BASE_URL          = {getattr(settings, "DEEPSEEK_BASE_URL", "")}')
        w(f'  DEEPSEEK_MODEL             = {getattr(settings, "DEEPSEEK_MODEL", "")}')

        w(self.style.MIGRATE_HEADING('Variables de entorno (lo que realmente ve el proceso)'))
        for nombre in ('DEEPSEEK_API_KEY', 'WHATSAPP_360_API_KEY', 'WHATSAPP_ACCESS_TOKEN',
                       'WHATSAPP_PHONE_NUMBER_ID', 'WHATSAPP_PROVIDER'):
            w(f'  {nombre:26s} = {"presente" if os.environ.get(nombre) else "AUSENTE"}')

        # URL que va a usar el cliente para enviar.
        w(self.style.MIGRATE_HEADING('Cliente de envío'))
        try:
            from whatsapp.services import WhatsAppClient
            cliente = WhatsAppClient()
            w(f'  provider   = {cliente.provider}')
            w(f'  POST       = {cliente.messages_url}')
            w(f'  credencial = {_mask(getattr(cliente, "api_key", None) or getattr(cliente, "access_token", ""))}')
        except Exception as exc:  # noqa: BLE001
            w(self.style.ERROR(f'  ✗ no se pudo construir el cliente: {exc}'))

        if opts.get('webhook'):
            w(self.style.MIGRATE_HEADING('Webhook registrado en 360dialog'))
            base = getattr(settings, 'WHATSAPP_360_BASE_URL', '').rstrip('/')
            try:
                resp = requests.get(
                    f'{base}/v1/configs/webhook',
                    headers={'D360-API-KEY': getattr(settings, 'WHATSAPP_360_API_KEY', '')},
                    timeout=15,
                )
                w(f'  GET {base}/v1/configs/webhook -> {resp.status_code}')
                w(f'  {resp.text[:500]}')
            except Exception as exc:  # noqa: BLE001
                w(self.style.ERROR(f'  ✗ {exc}'))

        if opts.get('agente'):
            wa_id = opts['agente']
            w(self.style.MIGRATE_HEADING(f'Agente (sin Celery) para wa_id={wa_id}'))
            try:
                from whatsapp.agent.orchestrator import responder_mensaje
                from whatsapp.models import ConversacionWhatsApp
                from whatsapp.services import _agente_habilitado

                conv = ConversacionWhatsApp.objects.filter(wa_id=wa_id).first()
                if conv is None:
                    w(self.style.WARNING('  no existe conversación para ese wa_id'))
                else:
                    w(f'  conv={conv.id} habilitado={_agente_habilitado(conv)} historial={len(conv.historial or [])}')
                    respuesta = responder_mensaje(conv, opts['texto'])
                    w(f'  respuesta: {respuesta[:500]}')
            except Exception as exc:  # noqa: BLE001
                w(self.style.ERROR(f'  ✗ {exc}'))

        if opts.get('enviar'):
            numero = opts['enviar']
            w(self.style.MIGRATE_HEADING(f'Envío de prueba a {numero}'))
            try:
                from whatsapp.services import enviar_mensaje_texto
                mensaje = enviar_mensaje_texto(numero, opts['texto'])
                color = self.style.SUCCESS if mensaje.estado == 'enviado' else self.style.ERROR
                w(color(f'  estado={mensaje.estado} wa_message_id={mensaje.wa_message_id}'))
                w(f'  payload={str(mensaje.payload)[:600]}')
            except Exception as exc:  # noqa: BLE001
                w(self.style.ERROR(f'  ✗ {exc}'))

        w(self.style.MIGRATE_HEADING('Últimos mensajes'))
        try:
            from whatsapp.models import WhatsAppMessage
            filtro = {}
            if opts.get('enviar'):
                filtro['wa_id'] = opts['enviar']
            for m in WhatsAppMessage.objects.filter(**filtro).order_by('-created_at')[: opts['ultimos']]:
                w(f'  {m.created_at:%Y-%m-%d %H:%M:%S} {m.direccion:9s} {m.estado:10s} {str(m.texto)[:60]!r}')
        except Exception as exc:  # noqa: BLE001
            w(self.style.WARNING(f'  no se pudieron leer los mensajes: {exc}'))
