import base64
import json
import logging

from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Plan, Subscripcion
from .serializers import (
    PlanSerializer,
    SubscripcionSerializer,
    SubscripcionCreateSerializer,
    UsuarioSubscripcionActivaSerializer,
)
from .services.app_store_service import get_app_store_service
from .services.google_play_service import get_google_play_service


logger = logging.getLogger(__name__)


class PlanListView(APIView):
    """
    GET /planes/
    Devuelve todos los planes activos. No requiere autenticación
    (la pantalla de listado de planes es pública).
    """

    def get(self, request):
        planes = Plan.objects.filter(activo=True).order_by('precio')
        serializer = PlanSerializer(planes, many=True)
        return Response(serializer.data)


class PlanDetailView(APIView):
    """
    GET /planes/<pk>/
    Detalle de un plan específico.
    """

    def get(self, request, pk):
        try:
            plan = Plan.objects.get(pk=pk, activo=True)
        except Plan.DoesNotExist:
            return Response({'detail': 'Plan no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = PlanSerializer(plan)
        return Response(serializer.data)


class SubscripcionCreateView(APIView):
    """
    POST /suscripciones/
    Crea una suscripción para el usuario autenticado.
    Body: { "plan_id": <id>, "expiracion": "<datetime>" }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data.copy()
        data['user_id'] = request.user.pk

        serializer = SubscripcionCreateSerializer(data=data)
        if serializer.is_valid():
            subscripcion = serializer.save()
            return Response(
                SubscripcionSerializer(subscripcion).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MiSubscripcionActivaView(APIView):
    """
    GET /suscripciones/mi-plan/
    Devuelve la suscripción activa del usuario logueado:
    plan, jobs restantes y fecha de expiración.
    Si no tiene suscripción activa devuelve 404.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        subscripcion = (
            Subscripcion.objects
            .filter(
                user_id=request.user,
                cancelada=False,
                expiracion__gt=timezone.now(),
            )
            .select_related('plan_id')
            .order_by('-created_at')
            .first()
        )

        if not subscripcion:
            return Response(
                {'detail': 'No tenés una suscripción activa.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = UsuarioSubscripcionActivaSerializer(subscripcion)
        return Response(serializer.data)


class CancelarSubscripcionView(APIView):
    """
    PATCH /suscripciones/<pk>/cancelar/
    Cancela la suscripción del usuario autenticado.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            subscripcion = Subscripcion.objects.get(pk=pk, user_id=request.user)
        except Subscripcion.DoesNotExist:
            return Response({'detail': 'Suscripción no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        if subscripcion.cancelada:
            return Response({'detail': 'La suscripción ya está cancelada.'}, status=status.HTTP_400_BAD_REQUEST)

        subscripcion.cancelada = True
        subscripcion.save()
        return Response({'detail': 'Suscripción cancelada correctamente.'})


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

class AdminSubscripcionListView(APIView):
    """
    GET /admin/suscripciones/
    Lista todas las suscripciones (solo admins).
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        subs = Subscripcion.objects.select_related('plan_id', 'user_id').order_by('-created_at')
        serializer = SubscripcionSerializer(subs, many=True)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# Google Play
# ---------------------------------------------------------------------------

class GooglePlaySubscribeView(APIView):
    """
    POST /suscripciones/google-play/subscribe/
    Body: { plan_id, purchase_token, product_id, package_name? }
    Verifica la compra contra Google Play y crea/actualiza la suscripción.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        plan_id = request.data.get('plan_id') or request.data.get('planId')
        purchase_token = request.data.get('purchase_token') or request.data.get('purchaseToken')
        product_id = request.data.get('product_id') or request.data.get('productId')

        missing = [
            field
            for field, value in (
                ('plan_id', plan_id),
                ('purchase_token', purchase_token),
                ('product_id', product_id),
            )
            if not value
        ]
        if missing:
            raise ValidationError(f'Faltan campos: {", ".join(missing)}')

        subscription = get_google_play_service().create_or_update_subscription(
            usuario=request.user,
            plan_id=plan_id,
            purchase_token=purchase_token,
            product_id=product_id,
        )
        return Response(
            UsuarioSubscripcionActivaSerializer(subscription).data,
            status=status.HTTP_200_OK,
        )


class GooglePlayCancelView(APIView):
    """
    DELETE /suscripciones/google-play/cancel/
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        get_google_play_service().cancel_subscription(request.user)
        return Response({'detail': 'Suscripción cancelada exitosamente.'})


class GooglePlayWebhookView(APIView):
    """
    POST /suscripciones/google-play/webhook/
    Pub/Sub envía mensajes con el payload en `message.data` (base64 JSON).
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        try:
            body = request.data if isinstance(request.data, dict) else {}
            pubsub_subscription = body.get('subscription', '')
            message = body.get('message') if isinstance(body, dict) else None

            logger.info(
                '📬 [GOOGLE PLAY WEBHOOK] POST recibido content_type=%s '
                'pubsub_subscription=%s body_keys=%s',
                request.content_type,
                pubsub_subscription or '(sin subscription)',
                list(body.keys()) if body else [],
            )

            if not message:
                logger.warning(
                    '⚠️ [GOOGLE PLAY WEBHOOK] Body sin "message" (¿ping manual?). body=%s',
                    body,
                )
                return Response(
                    {'received': True, 'processed': False, 'reason': 'no_message'},
                    status=status.HTTP_200_OK,
                )

            message_id = message.get('messageId')
            publish_time = message.get('publishTime')
            raw_data = message.get('data')

            if not raw_data:
                logger.warning(
                    '⚠️ [GOOGLE PLAY WEBHOOK] message sin data messageId=%s',
                    message_id,
                )
                return Response(
                    {'received': True, 'processed': False, 'reason': 'empty_data'},
                    status=status.HTTP_200_OK,
                )

            decoded = base64.b64decode(raw_data).decode('utf-8')
            logger.info(
                '📬 [GOOGLE PLAY WEBHOOK] Pub/Sub messageId=%s publishTime=%s '
                'decoded_len=%s preview=%s',
                message_id,
                publish_time,
                len(decoded),
                decoded[:500] + ('…' if len(decoded) > 500 else ''),
            )

            notification_data = json.loads(decoded)
            processed = get_google_play_service().process_webhook(notification_data)

            logger.info(
                '✅ [GOOGLE PLAY WEBHOOK] Fin request messageId=%s processed=%s',
                message_id,
                processed,
            )
            return Response(
                {'received': True, 'processed': processed, 'messageId': message_id},
                status=status.HTTP_200_OK,
            )
        except APIException:
            raise
        except Exception as exc:
            logger.exception('❌ [GOOGLE PLAY WEBHOOK] Error no controlado')
            return Response(
                {'received': False, 'error': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )


# ---------------------------------------------------------------------------
# App Store
# ---------------------------------------------------------------------------

class AppStoreSubscribeView(APIView):
    """
    POST /suscripciones/app-store/subscribe/
    Body: { plan_id, transaction_id, receipt_data }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        plan_id = request.data.get('plan_id') or request.data.get('planId')
        transaction_id = request.data.get('transaction_id') or request.data.get('transactionId')
        receipt_data = request.data.get('receipt_data') or request.data.get('receiptData')

        missing = [
            field
            for field, value in (
                ('plan_id', plan_id),
                ('transaction_id', transaction_id),
                ('receipt_data', receipt_data),
            )
            if not value
        ]
        if missing:
            raise ValidationError(f'Faltan campos: {", ".join(missing)}')

        subscription = get_app_store_service().create_or_update_subscription(
            usuario=request.user,
            plan_id=plan_id,
            receipt_data=receipt_data,
            transaction_id=transaction_id,
        )
        return Response(
            UsuarioSubscripcionActivaSerializer(subscription).data,
            status=status.HTTP_200_OK,
        )


class AppStoreCancelView(APIView):
    """
    DELETE /suscripciones/app-store/cancel/
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request):
        get_app_store_service().cancel_subscription(request.user)
        return Response({'detail': 'Suscripción cancelada exitosamente.'})


class AppStoreWebhookView(APIView):
    """
    POST /suscripciones/app-store/webhook/
    Procesa Server Notifications V2 de App Store.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        try:
            get_app_store_service().process_server_notification(request.data or {})
            return Response({'received': True}, status=status.HTTP_200_OK)
        except APIException:
            raise
        except Exception as exc:
            logger.exception('❌ Error procesando webhook de App Store')
            return Response(
                {'received': False, 'error': str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )