"""
Servicio para integración con Apple App Store / StoreKit.

Igual que Google Play, este servicio es tolerante a configuraciones
faltantes. Si no está `APP_STORE_SHARED_SECRET`, la app sigue
arrancando normal y los endpoints específicos (salvo testing local)
devuelven un mensaje claro al ser llamados.

Implementa:
  - Testing local con StoreKit Configuration File (transaction IDs cortos):
    igual que CoutureMock — no llama a Apple.
  - Validación del recibo (`/verifyReceipt`) con fallback sandbox <-> producción.
  - Registro/actualización de suscripciones en la base local.
  - Procesamiento de notificaciones de servidor (V2) decodificando
    `{ signedPayload: "<JWS>" }` como envía Apple.
"""

from __future__ import annotations

import base64
import json
import logging
import re
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Any, Optional

import requests
from django.conf import settings
from rest_framework.exceptions import APIException, ValidationError

from suscripciones.models import (
    Plan,
    Subscripcion,
    SubscripcionSource,
    SubscripcionStatus,
)
from usuario.models import Usuario


logger = logging.getLogger(__name__)


SANDBOX_URL = 'https://sandbox.itunes.apple.com/verifyReceipt'
PRODUCTION_URL = 'https://buy.itunes.apple.com/verifyReceipt'


class AppStoreService:
    def __init__(self) -> None:
        self.is_configured: bool = False
        self._shared_secret: Optional[str] = None
        self._environment: str = 'sandbox'
        self._init_error: Optional[str] = None
        self._initialize()

    def _initialize(self) -> None:
        shared_secret = getattr(settings, 'APP_STORE_SHARED_SECRET', '') or ''
        environment = (getattr(settings, 'APP_STORE_ENVIRONMENT', 'sandbox') or 'sandbox').lower()

        if not shared_secret:
            self._init_error = (
                '⚠️ App Store no configurado. Definí APP_STORE_SHARED_SECRET '
                'en el .env para habilitarlo (testing local StoreKit igual funciona).'
            )
            logger.warning(self._init_error)
            return

        self._shared_secret = shared_secret
        self._environment = environment if environment in ('sandbox', 'production') else 'sandbox'
        self.is_configured = True
        logger.info('✅ App Store configurado correctamente (%s)', self._environment)

    def _ensure_configured(self) -> None:
        if not self.is_configured:
            raise APIException(
                detail=self._init_error
                or 'App Store no está configurado. Verificá APP_STORE_SHARED_SECRET.',
                code='app_store_not_configured',
            )

    # ------------------------------------------------------------------
    # Local StoreKit Configuration File (simulador / Xcode)
    # ------------------------------------------------------------------

    @staticmethod
    def is_testing_transaction_id(transaction_id: str) -> bool:
        """
        Los IDs de StoreKit Configuration File suelen ser números chicos ("0","1","2")
        o contener "test". Igual criterio que CoutureMock.
        """
        tid = (transaction_id or '').strip()
        if not tid:
            return False
        if re.fullmatch(r'\d{1,3}', tid):
            return True
        return 'test' in tid.lower()

    def _mock_transaction_from_plan(self, plan: Plan, transaction_id: str) -> dict:
        now = datetime.now(tz=dt_timezone.utc)
        expires = now + (plan.duracion or timedelta(days=30))
        product_id = (plan.appstore_id or '').strip()
        return {
            'transaction_id': transaction_id,
            'original_transaction_id': transaction_id,
            'product_id': product_id,
            'expires_date_ms': str(int(expires.timestamp() * 1000)),
            'environment': 'LocalTesting',
        }

    # ------------------------------------------------------------------
    # Receipt / JWS verification
    # ------------------------------------------------------------------

    @staticmethod
    def _looks_like_jws(value: str) -> bool:
        parts = (value or '').strip().split('.')
        return len(parts) == 3 and all(parts)

    def transaction_from_jws(self, jws: str, expected_transaction_id: str) -> dict:
        """
        StoreKit 2 envía un JWS por transacción (no el recibo base64 clásico).
        Decodificamos el payload (mismo criterio que el webhook V2).
        """
        payload = self._decode_jwt(jws)
        tx_id = str(payload.get('transactionId') or '').strip()
        original_tx_id = str(payload.get('originalTransactionId') or tx_id).strip()
        product_id = str(payload.get('productId') or '').strip()
        expires_ms = payload.get('expiresDate')
        if expires_ms is None:
            expires_ms = payload.get('expires_date_ms')

        logger.info(
            '🍎 [APP STORE JWS] transactionId=%r original=%r productId=%r expiresDate=%r env=%r bundle=%r',
            tx_id,
            original_tx_id,
            product_id,
            expires_ms,
            payload.get('environment'),
            payload.get('bundleId'),
        )

        expected = str(expected_transaction_id or '').strip()
        if expected and expected not in (tx_id, original_tx_id):
            raise ValidationError('El JWS no corresponde a la transacción informada.')

        if not product_id:
            raise ValidationError('El JWS no incluye productId.')
        if not expires_ms:
            raise ValidationError('El JWS no incluye fecha de expiración.')

        bundle = (getattr(settings, 'APP_STORE_BUNDLE_ID', '') or '').strip()
        payload_bundle = str(payload.get('bundleId') or '').strip()
        if bundle and payload_bundle and bundle != payload_bundle:
            logger.warning(
                '🍎 [APP STORE JWS] bundle mismatch config=%r jws=%r',
                bundle,
                payload_bundle,
            )
            raise ValidationError('El bundle del JWS no coincide con la app.')

        return {
            'transaction_id': tx_id or expected,
            'original_transaction_id': original_tx_id or expected,
            'product_id': product_id,
            'expires_date_ms': str(int(expires_ms)),
            'environment': payload.get('environment') or self._environment,
        }

    def verify_receipt(self, receipt_data: str) -> dict:
        self._ensure_configured()
        url = PRODUCTION_URL if self._environment == 'production' else SANDBOX_URL
        body = {
            'receipt-data': receipt_data,
            # False: en upgrades/sandbox a veces la tx nueva no es la "latest" aún.
            'exclude-old-transactions': False,
            'password': self._shared_secret,
        }

        logger.info(
            '🍎 [APP STORE VERIFY] env=%s url=%s receipt_len=%s',
            self._environment,
            url,
            len(receipt_data or ''),
        )

        try:
            response = requests.post(url, json=body, timeout=15)
            response.raise_for_status()
            data = response.json() or {}
        except Exception as exc:
            logger.exception('❌ Error verificando recibo de App Store')
            raise ValidationError(f'Error al verificar el recibo: {exc}')

        status_code = data.get('status')
        logger.info(
            '🍎 [APP STORE VERIFY] apple_status=%s environment=%s latest_count=%s',
            status_code,
            data.get('environment'),
            len(data.get('latest_receipt_info') or []),
        )

        # 21007 = recibo de sandbox enviado a producción → reintentar en sandbox.
        if status_code == 21007 and self._environment == 'production':
            logger.info('🍎 [APP STORE VERIFY] status 21007 → reintento sandbox')
            try:
                fallback = requests.post(SANDBOX_URL, json=body, timeout=15)
                fallback.raise_for_status()
                data = fallback.json() or {}
                status_code = data.get('status')
                logger.info(
                    '🍎 [APP STORE VERIFY] sandbox fallback apple_status=%s latest_count=%s',
                    status_code,
                    len(data.get('latest_receipt_info') or []),
                )
            except Exception as exc:
                logger.exception('❌ Error en fallback sandbox')
                raise ValidationError(f'Error al verificar el recibo (sandbox): {exc}')

        if status_code != 0:
            logger.warning(
                '🍎 [APP STORE VERIFY] recibo rechazado apple_status=%s is_retryable=%s',
                status_code,
                data.get('is-retryable'),
            )
            raise ValidationError(f'Error verificando recibo: status {status_code}')

        return data

    # ------------------------------------------------------------------
    # Subscription handling
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_receipt_transactions(verification: dict) -> list[dict]:
        """Une latest_receipt_info + receipt.in_app sin duplicar transaction_id."""
        merged: list[dict] = []
        seen: set[str] = set()
        for source in (
            verification.get('latest_receipt_info') or [],
            (verification.get('receipt') or {}).get('in_app') or [],
        ):
            for tx in source:
                if not isinstance(tx, dict):
                    continue
                key = str(tx.get('transaction_id') or tx.get('original_transaction_id') or '')
                # Si no hay id, igual lo incluimos con clave sintética.
                dedupe = key or f'anon-{len(merged)}-{tx.get("product_id")}'
                if dedupe in seen:
                    continue
                seen.add(dedupe)
                merged.append(tx)

        def sort_key(tx: dict) -> int:
            try:
                return int(tx.get('expires_date_ms') or tx.get('purchase_date_ms') or 0)
            except (TypeError, ValueError):
                return 0

        merged.sort(key=sort_key, reverse=True)
        return merged

    @staticmethod
    def _pick_receipt_transaction(
        all_txs: list[dict],
        *,
        transaction_id: str,
        product_id: str,
    ) -> Optional[dict]:
        tid = (transaction_id or '').strip()
        pid = (product_id or '').strip()

        if tid:
            for tx in all_txs:
                if tx.get('transaction_id') == tid or tx.get('original_transaction_id') == tid:
                    return tx

        if pid:
            for tx in all_txs:
                if (tx.get('product_id') or '').strip() == pid and tx.get('expires_date_ms'):
                    logger.info(
                        '🍎 [APP STORE CREATE] match por product_id=%r (tx recibo=%r)',
                        pid,
                        tx.get('transaction_id'),
                    )
                    return tx

        # Último recurso: la suscripción más reciente del recibo (mismo grupo).
        for tx in all_txs:
            if tx.get('expires_date_ms') and tx.get('product_id'):
                logger.info(
                    '🍎 [APP STORE CREATE] fallback a tx más reciente product=%r tx=%r',
                    tx.get('product_id'),
                    tx.get('transaction_id'),
                )
                return tx
        return None

    def create_or_update_subscription(
        self,
        usuario: Usuario,
        plan_id: int,
        receipt_data: str,
        transaction_id: str,
    ) -> Subscripcion:
        logger.info(
            '🍎 [APP STORE CREATE] user_id=%s plan_id=%s transaction_id=%r receipt_len=%s configured=%s env=%s',
            getattr(usuario, 'pk', None),
            plan_id,
            transaction_id,
            len(receipt_data or ''),
            self.is_configured,
            self._environment,
        )

        plan = Plan.objects.filter(pk=plan_id, activo=True).first()
        if not plan:
            logger.warning('🍎 [APP STORE CREATE] plan_id=%s no encontrado/activo', plan_id)
            raise ValidationError('Plan no encontrado.')

        if not (plan.appstore_id or '').strip():
            logger.warning('🍎 [APP STORE CREATE] plan_id=%s sin appstore_id', plan_id)
            raise ValidationError('El plan no tiene appstore_id configurado.')

        transaction_id = str(transaction_id).strip()
        is_testing = self.is_testing_transaction_id(transaction_id)
        logger.info(
            '🍎 [APP STORE CREATE] plan=%s appstore_id=%r is_testing=%s',
            plan.nombre,
            plan.appstore_id,
            is_testing,
        )

        if is_testing:
            logger.info(
                '🧪 [APP STORE] Transaction ID de testing local detectado (%s) — sin verifyReceipt',
                transaction_id,
            )
            transaction = self._mock_transaction_from_plan(plan, transaction_id)
        else:
            if not receipt_data:
                logger.warning(
                    '🍎 [APP STORE CREATE] falta receipt_data/JWS (sandbox/prod) user_id=%s transaction_id=%r',
                    getattr(usuario, 'pk', None),
                    transaction_id,
                )
                raise ValidationError(
                    'Falta receipt_data (JWS StoreKit 2 o recibo) para verificar la compra.'
                )

            if self._looks_like_jws(receipt_data):
                logger.info('🍎 [APP STORE CREATE] receipt_data es JWS (StoreKit 2)')
                transaction = self.transaction_from_jws(receipt_data, transaction_id)
            else:
                verification = self.verify_receipt(receipt_data)
                all_txs = self._collect_receipt_transactions(verification)
                if not all_txs:
                    logger.warning(
                        '🍎 [APP STORE CREATE] recibo sin transacciones keys=%s',
                        list(verification.keys()),
                    )
                    raise ValidationError('No se encontró información de suscripción en el recibo.')

                summary = [
                    {
                        'transaction_id': tx.get('transaction_id'),
                        'original_transaction_id': tx.get('original_transaction_id'),
                        'product_id': tx.get('product_id'),
                        'expires_date_ms': tx.get('expires_date_ms'),
                    }
                    for tx in all_txs[:12]
                ]
                logger.info(
                    '🍎 [APP STORE CREATE] buscando transaction_id=%r product=%r en %s txs: %s',
                    transaction_id,
                    plan.appstore_id,
                    len(all_txs),
                    summary,
                )

                transaction = self._pick_receipt_transaction(
                    all_txs,
                    transaction_id=transaction_id,
                    product_id=(plan.appstore_id or '').strip(),
                )
                if not transaction:
                    products = sorted({
                        str(tx.get('product_id') or '')
                        for tx in all_txs
                        if tx.get('product_id')
                    })
                    logger.warning(
                        '🍎 [APP STORE CREATE] no match tx=%r product=%r available=%s',
                        transaction_id,
                        plan.appstore_id,
                        products,
                    )
                    raise ValidationError(
                        'Transacción no encontrada en el recibo. '
                        f'Productos en recibo: {", ".join(products) or "ninguno"}.'
                    )

            receipt_product = (transaction.get('product_id') or '').strip()
            plan_product = (plan.appstore_id or '').strip()
            if receipt_product and plan_product and receipt_product != plan_product:
                # En el mismo subscription group Apple puede devolver la tx/producto
                # realmente activo (ej. monthly) aunque el FE pidió Pro.
                alt_plan = Plan.objects.filter(appstore_id=receipt_product, activo=True).first()
                if alt_plan:
                    logger.warning(
                        '🍎 [APP STORE CREATE] plan ajustado %s(%s) → %s(%s) según recibo',
                        plan.nombre,
                        plan_product,
                        alt_plan.nombre,
                        receipt_product,
                    )
                    plan = alt_plan
                else:
                    logger.warning(
                        '🍎 [APP STORE CREATE] product mismatch plan.appstore_id=%r receipt.product_id=%r',
                        plan_product,
                        receipt_product,
                    )
                    raise ValidationError('El producto no coincide con el plan.')

        expires_ms = transaction.get('expires_date_ms')
        if not expires_ms:
            logger.warning(
                '🍎 [APP STORE CREATE] tx sin expires_date_ms keys=%s',
                list(transaction.keys()),
            )
            raise ValidationError('La transacción no tiene fecha de expiración.')

        expiration = datetime.fromtimestamp(int(expires_ms) / 1000, tz=dt_timezone.utc)

        subscription = (
            Subscripcion.objects.filter(user_id=usuario)
            .order_by('-created_at')
            .first()
        )
        if subscription:
            subscription.source = SubscripcionSource.APP_STORE
            subscription.appstore_transaction_id = transaction.get('transaction_id')
            subscription.appstore_original_transaction_id = transaction.get('original_transaction_id')
            subscription.expiracion = expiration
            subscription.plan_id = plan
            subscription.status = SubscripcionStatus.ACTIVE
            subscription.cancelada = False
            subscription.jobs_restantes = plan.cantidad_jobs
        else:
            subscription = Subscripcion(
                user_id=usuario,
                plan_id=plan,
                source=SubscripcionSource.APP_STORE,
                appstore_transaction_id=transaction.get('transaction_id'),
                appstore_original_transaction_id=transaction.get('original_transaction_id'),
                expiracion=expiration,
                status=SubscripcionStatus.ACTIVE,
                jobs_restantes=plan.cantidad_jobs,
            )

        subscription.save()
        logger.info(
            '🍎 [APP STORE] Suscripción guardada para usuario %s (plan %s, expira %s, testing=%s)',
            usuario.pk,
            plan.nombre,
            expiration.isoformat(),
            is_testing,
        )
        return subscription

    def cancel_subscription(self, usuario: Usuario) -> Subscripcion:
        subscription = (
            Subscripcion.objects.filter(
                user_id=usuario,
                source=SubscripcionSource.APP_STORE,
            )
            .order_by('-created_at')
            .first()
        )
        if not subscription:
            raise ValidationError('No hay suscripción activa de App Store.')

        subscription.status = SubscripcionStatus.CANCELED
        subscription.cancelada = True
        subscription.save(update_fields=['status', 'cancelada', 'updated_at'])
        logger.info('✅ [APP STORE] Suscripción %s cancelada', subscription.pk)
        return subscription

    # ------------------------------------------------------------------
    # Server notifications V2
    # ------------------------------------------------------------------

    @staticmethod
    def _decode_jwt(token: str) -> dict:
        """Decodifica un JWT SIN verificar la firma."""
        try:
            parts = token.split('.')
            if len(parts) != 3:
                raise ValueError('Token JWT inválido')
            payload = parts[1] + '=' * (-len(parts[1]) % 4)
            decoded = base64.urlsafe_b64decode(payload.encode('utf-8'))
            return json.loads(decoded.decode('utf-8'))
        except Exception as exc:
            logger.exception('Error decodificando JWT')
            raise ValidationError(f'Token inválido: {exc}')

    NOTIFICATION_TYPES = {
        'SUBSCRIBED': SubscripcionStatus.ACTIVE,
        'DID_RENEW': SubscripcionStatus.ACTIVE,
        'DID_FAIL_TO_RENEW': SubscripcionStatus.PAST_DUE,
        'GRACE_PERIOD_EXPIRED': SubscripcionStatus.EXPIRED,
        'EXPIRED': SubscripcionStatus.EXPIRED,
        'REFUND': SubscripcionStatus.REFUNDED,
        'REVOKE': SubscripcionStatus.CANCELED,
    }

    def process_server_notification(self, notification_payload: dict[str, Any]) -> None:
        """
        Apple envía `{ "signedPayload": "<JWS>" }`. Decodificamos ese JWS
        y recién ahí leemos notificationType / data.signedTransactionInfo.
        """
        payload = notification_payload or {}
        if isinstance(payload.get('signedPayload'), str) and payload['signedPayload']:
            try:
                payload = self._decode_jwt(payload['signedPayload'])
            except Exception:
                logger.exception('❌ [APP STORE] No se pudo decodificar signedPayload')
                return

        notification_type = payload.get('notificationType')
        subtype = payload.get('subtype')
        data = payload.get('data') or {}
        signed_transaction_info = data.get('signedTransactionInfo')
        if not signed_transaction_info:
            logger.info(
                '🔔 [APP STORE] Notificación sin signedTransactionInfo (tipo=%s subtype=%s)',
                notification_type,
                subtype,
            )
            return

        transaction_info = self._decode_jwt(signed_transaction_info)
        original_transaction_id = transaction_info.get('originalTransactionId')

        subscription = (
            Subscripcion.objects.filter(
                appstore_original_transaction_id=original_transaction_id
            )
            .order_by('-created_at')
            .first()
        )
        if not subscription:
            logger.info('🔔 [APP STORE] Webhook sin suscripción asociada')
            return

        update_fields = ['updated_at']

        new_status: Optional[SubscripcionStatus] = self.NOTIFICATION_TYPES.get(notification_type)

        if notification_type == 'DID_CHANGE_RENEWAL_STATUS':
            if subtype == 'AUTO_RENEW_ENABLED':
                new_status = SubscripcionStatus.ACTIVE
            elif subtype == 'AUTO_RENEW_DISABLED':
                new_status = SubscripcionStatus.CANCELED

        if notification_type == 'EXPIRED' and subtype == 'VOLUNTARY':
            new_status = SubscripcionStatus.CANCELED

        if new_status:
            subscription.status = new_status
            update_fields.append('status')
            if new_status in (
                SubscripcionStatus.CANCELED,
                SubscripcionStatus.EXPIRED,
                SubscripcionStatus.REFUNDED,
            ):
                subscription.cancelada = True
                update_fields.append('cancelada')

        if notification_type in ('SUBSCRIBED', 'DID_RENEW'):
            transaction_id = transaction_info.get('transactionId')
            expires_date = transaction_info.get('expiresDate')
            if transaction_id:
                subscription.appstore_transaction_id = transaction_id
                update_fields.append('appstore_transaction_id')
            if expires_date:
                subscription.expiracion = datetime.fromtimestamp(
                    int(expires_date) / 1000, tz=dt_timezone.utc
                )
                update_fields.append('expiracion')

        subscription.save(update_fields=update_fields)
        logger.info(
            '🔔 [APP STORE] Suscripción %s → %s (tipo %s/%s)',
            subscription.pk,
            new_status or 'sin cambios',
            notification_type,
            subtype,
        )


_service_instance: Optional[AppStoreService] = None


def get_app_store_service() -> AppStoreService:
    global _service_instance
    if _service_instance is None:
        _service_instance = AppStoreService()
    return _service_instance
