import hashlib
import hmac
import logging

from django.conf import settings
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from . import services
from .models import WhatsAppMessage
from .serializers import EnviarMensajeSerializer, WhatsAppMessageSerializer

logger = logging.getLogger(__name__)


def _verificar_firma_meta(request) -> bool:
    """
    Verifica la firma HMAC (X-Hub-Signature-256) que manda Meta Cloud API en cada
    POST, calculada con el App Secret. Si no hay App Secret configurado, no se exige
    (útil mientras se prueba en sandbox/dev).
    """
    app_secret = settings.WHATSAPP_APP_SECRET
    if not app_secret:
        return True
    firma = request.headers.get('X-Hub-Signature-256', '')
    if not firma.startswith('sha256='):
        return False
    esperada = hmac.new(app_secret.encode(), request.body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(firma[len('sha256='):], esperada)


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def whatsapp_webhook(request):
    """Endpoint que recibe los webhooks (mensajes entrantes y estados) de WhatsApp Cloud API (Meta)."""
    if request.method == 'GET':
        # Handshake de verificación de Meta Cloud API.
        # Devuelve HttpResponse plano (no DRF Response) para que el
        # StandardizedResponseMiddleware no envuelva el body en {ok, message, data}:
        # Meta exige que el body sea EXACTAMENTE el valor de hub.challenge.
        mode = request.query_params.get('hub.mode')
        token = request.query_params.get('hub.verify_token')
        challenge = request.query_params.get('hub.challenge', '')

        es_valido = mode == 'subscribe' and settings.WHATSAPP_WEBHOOK_TOKEN and token == settings.WHATSAPP_WEBHOOK_TOKEN
        logger.info(
            "Verificacion webhook WhatsApp: mode=%r token_recibido=%r token_esperado=%r challenge=%r resultado=%s",
            mode, token, settings.WHATSAPP_WEBHOOK_TOKEN, challenge, 'OK' if es_valido else 'RECHAZADO',
        )

        if es_valido:
            return HttpResponse(challenge, content_type='text/plain', status=200)
        return HttpResponse('Verification failed', status=403)

    if not _verificar_firma_meta(request):
        logger.warning("Webhook WhatsApp con firma inválida rechazado")
        return Response(status=status.HTTP_403_FORBIDDEN)

    data = request.data
    logger.info("Webhook WhatsApp recibido: %s", data)
    try:
        services.procesar_webhook_payload(data)
    except Exception:
        logger.exception("Error procesando webhook de WhatsApp")
    return Response(status=status.HTTP_200_OK)


class WhatsAppMessageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WhatsAppMessage.objects.all()
    serializer_class = WhatsAppMessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        wa_id = self.request.query_params.get('wa_id')
        if wa_id:
            queryset = queryset.filter(wa_id=wa_id)
        return queryset

    @action(detail=False, methods=['post'], url_path='enviar')
    def enviar(self, request):
        serializer = EnviarMensajeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mensaje = services.enviar_mensaje_texto(
            to=serializer.validated_data['to'],
            body=serializer.validated_data['body'],
        )
        return Response(
            WhatsAppMessageSerializer(mensaje).data,
            status=status.HTTP_201_CREATED if mensaje.estado != WhatsAppMessage.ESTADO_FALLIDO else status.HTTP_502_BAD_GATEWAY,
        )
