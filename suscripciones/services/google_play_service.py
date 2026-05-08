"""
Servicio para integración con Google Play Billing.

Diseñado para ser tolerante a configuraciones faltantes: si no están
las variables de entorno (`GOOGLE_SERVICE_ACCOUNT_KEY` /
`GOOGLE_PLAY_PACKAGE_NAME`) o si la librería `googleapiclient` no está
instalada, el servicio se inicializa marcado como `is_configured=False`.
La app sigue arrancando normalmente y solo los endpoints que requieren
Google Play devuelven un error claro cuando se llaman.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone as dt_timezone
from typing import Any, Optional

from django.conf import settings
from django.utils import timezone

from rest_framework.exceptions import ValidationError, APIException

from suscripciones.models import (
    Plan,
    Subscripcion,
    SubscripcionSource,
    SubscripcionStatus,
)
from usuario.models import Usuario


logger = logging.getLogger(__name__)


class GooglePlayService:
    """Wrapper sobre Google Play Developer API (`androidpublisher` v3)."""

    def __init__(self) -> None:
        self.is_configured: bool = False
        self._publisher = None
        self._package_name: Optional[str] = None
        self._init_error: Optional[str] = None
        self._initialize()

    def _initialize(self) -> None:
        service_account_key_json = getattr(settings, 'GOOGLE_SERVICE_ACCOUNT_KEY', '') or ''
        package_name = getattr(settings, 'GOOGLE_PLAY_PACKAGE_NAME', '') or ''

        if not service_account_key_json or not package_name:
            self._init_error = (
                '⚠️ Google Play no configurado. Definí GOOGLE_SERVICE_ACCOUNT_KEY '
                'y GOOGLE_PLAY_PACKAGE_NAME en el .env para habilitarlo.'
            )
            logger.warning(self._init_error)
            return

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
        except ImportError as exc:
            self._init_error = (
                '⚠️ Google Play no inicializado: faltan dependencias '
                f'`google-api-python-client` / `google-auth` ({exc}).'
            )
            logger.warning(self._init_error)
            return

        try:
            credentials_dict = json.loads(service_account_key_json)
            credentials = service_account.Credentials.from_service_account_info(
                credentials_dict,
                scopes=['https://www.googleapis.com/auth/androidpublisher'],
            )
            self._publisher = build('androidpublisher', 'v3', credentials=credentials, cache_discovery=False)
            self._package_name = package_name
            self.is_configured = True
            logger.info('✅ Google Play configurado correctamente')
        except Exception as exc:
            self._init_error = f'❌ Error configurando Google Play: {exc}'
            logger.exception(self._init_error)

    def _ensure_configured(self) -> None:
        if not self.is_configured or not self._publisher or not self._package_name:
            raise APIException(
                detail=self._init_error
                or 'Google Play no está configurado. Verificá las credenciales.',
                code='google_play_not_configured',
            )

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def verify_purchase(self, purchase_token: str, product_id: str) -> dict:
        """Consulta a Google Play el detalle de la compra."""
        self._ensure_configured()
        try:
            response = (
                self._publisher.purchases()
                .subscriptions()
                .get(
                    packageName=self._package_name,
                    subscriptionId=product_id,
                    token=purchase_token,
                )
                .execute()
            )
            return response or {}
        except Exception as exc:
            logger.exception('❌ Error verificando compra de Google Play')
            raise ValidationError(f'Error al verificar la compra: {exc}')

    def create_or_update_subscription(
        self,
        usuario: Usuario,
        plan_id: int,
        purchase_token: str,
        product_id: str,
    ) -> Subscripcion:
        plan = Plan.objects.filter(pk=plan_id, activo=True).first()
        if not plan:
            raise ValidationError('Plan no encontrado.')

        if (plan.google_play_id or '').strip() != (product_id or '').strip():
            raise ValidationError('El producto no coincide con el plan.')

        purchase_data = self.verify_purchase(purchase_token, product_id)

        # paymentState: 0 pending, 1 paid, 2 free trial, 3 upgrade pending
        payment_state = purchase_data.get('paymentState')
        if payment_state not in (1, 2):
            raise ValidationError(
                f'Estado de pago no válido: {payment_state}. '
                'Se esperaba pagado (1) o trial (2).'
            )

        is_trial = payment_state == 2

        expiry_millis = purchase_data.get('expiryTimeMillis')
        if not expiry_millis:
            raise ValidationError('Google Play no devolvió la fecha de expiración.')
        expiration = datetime.fromtimestamp(int(expiry_millis) / 1000, tz=dt_timezone.utc)

        subscription = (
            Subscripcion.objects.filter(user_id=usuario)
            .order_by('-created_at')
            .first()
        )
        status_value = (
            SubscripcionStatus.TRIALING if is_trial else SubscripcionStatus.ACTIVE
        )

        if subscription:
            subscription.source = SubscripcionSource.GOOGLE_PLAY
            subscription.google_play_subscription_id = product_id
            subscription.google_play_purchase_token = purchase_token
            subscription.expiracion = expiration
            subscription.plan_id = plan
            subscription.status = status_value
            subscription.cancelada = False
            subscription.jobs_restantes = plan.cantidad_jobs
        else:
            subscription = Subscripcion(
                user_id=usuario,
                plan_id=plan,
                source=SubscripcionSource.GOOGLE_PLAY,
                google_play_subscription_id=product_id,
                google_play_purchase_token=purchase_token,
                expiracion=expiration,
                status=status_value,
                jobs_restantes=plan.cantidad_jobs,
            )

        subscription.save()
        logger.info(
            '📱 [GOOGLE PLAY] Suscripción %s para usuario %s (plan %s, expira %s)',
            'TRIAL' if is_trial else 'ACTIVA',
            usuario.pk,
            plan.nombre,
            expiration.isoformat(),
        )
        return subscription

    def cancel_subscription(self, usuario: Usuario) -> Subscripcion:
        subscription = (
            Subscripcion.objects.filter(
                user_id=usuario,
                source=SubscripcionSource.GOOGLE_PLAY,
            )
            .order_by('-created_at')
            .first()
        )
        if not subscription:
            raise ValidationError('No hay suscripción activa de Google Play.')

        subscription.status = SubscripcionStatus.CANCELED
        subscription.cancelada = True
        subscription.save(update_fields=['status', 'cancelada', 'updated_at'])
        logger.info('✅ [GOOGLE PLAY] Suscripción %s cancelada', subscription.pk)
        return subscription

    # ------------------------------------------------------------------
    # Webhook
    # ------------------------------------------------------------------

    NOTIFICATION_TYPES = {
        1: SubscripcionStatus.ACTIVE,        # SUBSCRIPTION_RECOVERED
        2: SubscripcionStatus.ACTIVE,        # SUBSCRIPTION_RENEWED
        3: SubscripcionStatus.CANCELED,      # SUBSCRIPTION_CANCELED
        4: SubscripcionStatus.ACTIVE,        # SUBSCRIPTION_PURCHASED
        5: SubscripcionStatus.PAST_DUE,      # SUBSCRIPTION_ON_HOLD
        6: SubscripcionStatus.PAST_DUE,      # SUBSCRIPTION_IN_GRACE_PERIOD
        7: SubscripcionStatus.ACTIVE,        # SUBSCRIPTION_RESTARTED
        10: SubscripcionStatus.PAUSED,       # SUBSCRIPTION_PAUSED
        12: SubscripcionStatus.CANCELED,     # SUBSCRIPTION_REVOKED
        13: SubscripcionStatus.EXPIRED,      # SUBSCRIPTION_EXPIRED
    }

    def process_webhook(self, notification_data: dict[str, Any]) -> None:
        sub_notification = (notification_data or {}).get('subscriptionNotification')
        if not sub_notification:
            return

        purchase_token = sub_notification.get('purchaseToken')
        subscription_id = sub_notification.get('subscriptionId')
        notification_type = sub_notification.get('notificationType')

        subscription = (
            Subscripcion.objects.filter(google_play_purchase_token=purchase_token)
            .order_by('-created_at')
            .first()
        )
        if not subscription:
            logger.info('🔔 [GOOGLE PLAY] Webhook sin suscripción asociada')
            return

        new_status = self.NOTIFICATION_TYPES.get(notification_type)
        if new_status is None:
            logger.info(
                '🔔 [GOOGLE PLAY] Notificación %s sin manejo específico', notification_type
            )
            return

        update_fields = ['status', 'updated_at']
        subscription.status = new_status

        if notification_type in (1, 2, 4, 7) and self.is_configured:
            try:
                purchase_data = self.verify_purchase(purchase_token, subscription_id)
                expiry_millis = purchase_data.get('expiryTimeMillis')
                if expiry_millis:
                    subscription.expiracion = datetime.fromtimestamp(
                        int(expiry_millis) / 1000, tz=dt_timezone.utc
                    )
                    update_fields.append('expiracion')
            except Exception:
                logger.exception('⚠️ [GOOGLE PLAY] No se pudo refrescar expiración')

        if new_status in (SubscripcionStatus.CANCELED, SubscripcionStatus.EXPIRED):
            subscription.cancelada = True
            update_fields.append('cancelada')

        subscription.save(update_fields=update_fields)
        logger.info(
            '🔔 [GOOGLE PLAY] Suscripción %s → %s (tipo %s)',
            subscription.pk,
            new_status,
            notification_type,
        )


# Singleton perezoso para evitar múltiples handshakes con Google.
_service_instance: Optional[GooglePlayService] = None


def get_google_play_service() -> GooglePlayService:
    global _service_instance
    if _service_instance is None:
        _service_instance = GooglePlayService()
    return _service_instance
