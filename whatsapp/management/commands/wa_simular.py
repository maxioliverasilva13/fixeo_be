"""Simula un mensaje entrante de WhatsApp SIN pasar por Meta.

Sirve para probar el agente (DeepSeek + tools + DB) en local/staging sin tocar
el número ni el webhook de producción.

Ejemplos:
  # Ver la respuesta del agente a un texto (no envía nada por WhatsApp):
  python manage.py wa_simular --from 59899123456 --text "busco un plomero cerca"

  # Fijar ubicación (como si compartiera su location por el clip):
  python manage.py wa_simular --from 59899123456 --lat -34.9011 --lon -56.1645

  # Ejecutar la cadena completa como si llegara el webhook real
  # (crea WhatsAppMessage, aplica dedupe y encola/ejecuta la task):
  python manage.py wa_simular --from 59899123456 --text "hola" --webhook
"""
import uuid

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Simula un mensaje entrante de WhatsApp sin pasar por Meta.'

    def add_arguments(self, parser):
        parser.add_argument('--from', dest='wa_id', required=True,
                            help='Número del remitente (wa_id), ej. 59899123456')
        parser.add_argument('--text', dest='text', default=None, help='Texto del mensaje.')
        parser.add_argument('--lat', type=float, default=None, help='Latitud (mensaje de ubicación).')
        parser.add_argument('--lon', type=float, default=None, help='Longitud (mensaje de ubicación).')
        parser.add_argument('--webhook', action='store_true',
                            help='Pasa por procesar_webhook_payload() (cadena completa, dedupe, task).')

    def handle(self, *args, **opts):
        from whatsapp import services

        wa_id = opts['wa_id']
        texto = opts['text']
        lat, lon = opts['lat'], opts['lon']

        if opts['webhook']:
            payload = self._build_meta_payload(wa_id, texto, lat, lon)
            self.stdout.write(self.style.WARNING('→ Enviando por procesar_webhook_payload()...'))
            services.procesar_webhook_payload(payload)
            self.stdout.write(self.style.SUCCESS(
                'Listo. Si CELERY_TASK_ALWAYS_EAGER no está activo, la respuesta '
                'la genera el worker de Celery; revisá sus logs.'
            ))
            return

        # Modo directo (sin Meta, sin worker): corre el agente e imprime la respuesta.
        from whatsapp.agent.orchestrator import responder_mensaje

        conv = services.obtener_o_crear_conversacion(wa_id)

        if lat is not None and lon is not None:
            from decimal import Decimal
            conv.ubicacion_lat = Decimal(str(lat))
            conv.ubicacion_lon = Decimal(str(lon))
            if conv.estado == conv.ESTADO_ESPERANDO_UBICACION:
                conv.estado = conv.ESTADO_IDLE
            conv.save(update_fields=['ubicacion_lat', 'ubicacion_lon', 'estado', 'ultima_actividad'])
            self.stdout.write(self.style.SUCCESS(f'Ubicación fijada: {lat}, {lon}'))
            if not texto:
                texto = 'Te comparto mi ubicación.'

        if not texto:
            self.stdout.write(self.style.ERROR('Nada que procesar: pasá --text o --lat/--lon.'))
            return

        self.stdout.write(self.style.HTTP_INFO(f'\n👤 Usuario: {texto}'))
        respuesta = responder_mensaje(conv, texto)
        self.stdout.write(self.style.SUCCESS(f'🤖 Agente: {respuesta}\n'))
        self.stdout.write(
            f'(conv_id={conv.id} flujo={conv.flujo} estado={conv.estado} '
            f'usuario_id={conv.usuario_id} ubicacion={conv.tiene_ubicacion})'
        )

    def _build_meta_payload(self, wa_id, texto, lat, lon):
        msg = {'from': wa_id, 'id': f'wamid.SIM{uuid.uuid4().hex[:16]}', 'timestamp': '0'}
        if lat is not None and lon is not None:
            msg['type'] = 'location'
            msg['location'] = {'latitude': lat, 'longitude': lon}
        else:
            msg['type'] = 'text'
            msg['text'] = {'body': texto or ''}
        return {
            'object': 'whatsapp_business_account',
            'entry': [{
                'id': '0',
                'changes': [{
                    'field': 'messages',
                    'value': {
                        'messaging_product': 'whatsapp',
                        'metadata': {'display_phone_number': '000', 'phone_number_id': '0'},
                        'contacts': [{'profile': {'name': 'Tester'}, 'wa_id': wa_id}],
                        'messages': [msg],
                    },
                }],
            }],
        }
