"""Gestiona el webhook de 360dialog Cloud API.

360dialog no usa el handshake GET de Meta: el webhook se registra por API con un
POST a {base}/v1/configs/webhook usando el header D360-API-KEY.

Ejemplos:
    # Ver el webhook configurado actualmente
    python manage.py webhook_360 --get

    # Registrar el webhook (usa la URL pasada o WHATSAPP_WEBHOOK_URL de settings)
    python manage.py webhook_360 --set https://mi-dominio.com/api/whatsapp/webhook

    # Registrar agregando el token de protección de URL configurado
    python manage.py webhook_360 --set https://mi-dominio.com/api/whatsapp/webhook --con-token
"""

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Registra o consulta el webhook de WhatsApp en 360dialog Cloud API."

    def add_arguments(self, parser):
        parser.add_argument('--set', dest='url', help='URL pública HTTPS del webhook a registrar.')
        parser.add_argument('--get', action='store_true', help='Muestra el webhook configurado.')
        parser.add_argument(
            '--con-token', action='store_true',
            help='Agrega ?token=WHATSAPP_WEBHOOK_URL_TOKEN a la URL registrada.',
        )

    def _headers(self):
        api_key = settings.WHATSAPP_360_API_KEY
        if not api_key:
            raise CommandError('WHATSAPP_360_API_KEY no está configurada en settings/.env')
        return {'D360-API-KEY': api_key, 'Content-Type': 'application/json'}

    def handle(self, *args, **opts):
        base = settings.WHATSAPP_360_BASE_URL.rstrip('/')
        endpoint = f"{base}/v1/configs/webhook"

        if opts.get('url') is None and not opts.get('get'):
            raise CommandError('Indicá --get o --set <url>.')

        if opts.get('get'):
            resp = requests.get(endpoint, headers=self._headers(), timeout=15)
            self.stdout.write(f"GET {endpoint} -> {resp.status_code}")
            self.stdout.write(resp.text)
            return

        url = opts['url']
        if opts.get('con_token'):
            token = settings.WHATSAPP_WEBHOOK_URL_TOKEN
            if not token:
                raise CommandError('WHATSAPP_WEBHOOK_URL_TOKEN no está configurada.')
            sep = '&' if '?' in url else '?'
            url = f"{url}{sep}token={token}"

        resp = requests.post(endpoint, json={'url': url}, headers=self._headers(), timeout=15)
        self.stdout.write(f"POST {endpoint} url={url} -> {resp.status_code}")
        self.stdout.write(resp.text)
        if resp.ok:
            self.stdout.write(self.style.SUCCESS('Webhook registrado correctamente.'))
        else:
            raise CommandError(f'360dialog rechazó el registro ({resp.status_code}).')
