import logging

from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from carritos.models import Orden
from trabajos.models import Trabajo
from .models import Pago, Tarjeta
from .serializers import (
    PagoSerializer, PagoResumenSerializer, TarjetaSerializer,
    GuardarTarjetaSerializer, PagoDirectoSerializer,
)
from . import services

logger = logging.getLogger(__name__)


class PagoViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PagoSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        queryset = Pago.objects.filter(usuario=user)

        tipo = self.request.query_params.get('tipo')
        if tipo:
            queryset = queryset.filter(tipo=tipo)

        entidad_status = self.request.query_params.get('status')
        if entidad_status:
            queryset = queryset.filter(status=entidad_status)

        return queryset

    # ------------------------------------------------------------------
    # Pago directo (transparent checkout)
    # ------------------------------------------------------------------

    @action(detail=False, methods=['post'], url_path='pagar')
    def pagar(self, request):
        """Procesa un pago inline usando card_token (sin redirección)."""
        serializer = PagoDirectoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        orden = None
        trabajo = None

        if data['tipo'] == 'orden':
            try:
                orden = Orden.objects.get(id=data['orden_id'], usuario=request.user)
            except Orden.DoesNotExist:
                return Response({'error': 'Orden no encontrada'}, status=status.HTTP_404_NOT_FOUND)

        elif data['tipo'] == 'trabajo':
            try:
                trabajo = Trabajo.objects.get(id=data['trabajo_id'], usuario=request.user)
            except Trabajo.DoesNotExist:
                return Response({'error': 'Trabajo no encontrado'}, status=status.HTTP_404_NOT_FOUND)
            if not trabajo.precio_final:
                return Response(
                    {'error': 'El trabajo no tiene precio definido'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        try:
            from .models import MercadoPagoCustomer

            mp_customer_id = ''
            try:
                mp_cust = MercadoPagoCustomer.objects.get(usuario=request.user)
                mp_customer_id = mp_cust.mp_customer_id
            except MercadoPagoCustomer.DoesNotExist:
                pass

            logger.info(
                "Pagar request: tipo=%s, pm=%s, issuer=%s, installments=%s, saved=%s",
                data['tipo'],
                data.get('payment_method_id', '(no enviado)'),
                data.get('issuer_id', '(no enviado)'),
                data.get('installments', 1),
                data.get('is_saved_card', False),
            )
            resultado = services.crear_pago_directo(
                usuario=request.user,
                card_token=data['card_token'],
                payment_method_id=data.get('payment_method_id', ''),
                issuer_id=data.get('issuer_id', ''),
                installments=data.get('installments', 1),
                tipo=data['tipo'],
                orden=orden,
                trabajo=trabajo,
                bin_tarjeta=data.get('bin', ''),
                mp_customer_id=mp_customer_id,
                payment_method_type=data.get('payment_method_type', ''),
            )
            return Response(resultado, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.exception("Error procesando pago directo")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # ------------------------------------------------------------------
    # Preferencias (Checkout Pro - fallback para WebView)
    # ------------------------------------------------------------------

    @action(detail=False, methods=['post'], url_path='crear-preferencia-orden')
    def crear_preferencia_orden(self, request):
        orden_id = request.data.get('orden_id')
        if not orden_id:
            return Response({'error': 'orden_id requerido'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            orden = Orden.objects.get(id=orden_id, usuario=request.user)
        except Orden.DoesNotExist:
            return Response({'error': 'Orden no encontrada'}, status=status.HTTP_404_NOT_FOUND)

        pago_existente = Pago.objects.filter(
            orden=orden, tipo='orden', status__in=['pendiente', 'aprobado']
        ).first()
        if pago_existente and pago_existente.mp_preference_id:
            return Response({
                'preference_id': pago_existente.mp_preference_id,
                'pago_id': pago_existente.id,
                'message': 'Ya existe una preferencia para esta orden',
            })

        try:
            resultado = services.crear_preferencia_orden(orden, request)
            return Response(resultado, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.exception("Error creando preferencia para orden %s", orden_id)
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['post'], url_path='crear-preferencia-trabajo')
    def crear_preferencia_trabajo(self, request):
        trabajo_id = request.data.get('trabajo_id')
        if not trabajo_id:
            return Response({'error': 'trabajo_id requerido'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            trabajo = Trabajo.objects.get(id=trabajo_id, usuario=request.user)
        except Trabajo.DoesNotExist:
            return Response({'error': 'Trabajo no encontrado'}, status=status.HTTP_404_NOT_FOUND)

        if not trabajo.precio_final:
            return Response(
                {'error': 'El trabajo no tiene precio definido'},
                status=status.HTTP_400_BAD_REQUEST
            )

        pago_existente = Pago.objects.filter(
            trabajo=trabajo, tipo='trabajo', status__in=['pendiente', 'aprobado']
        ).first()
        if pago_existente and pago_existente.mp_preference_id:
            return Response({
                'preference_id': pago_existente.mp_preference_id,
                'pago_id': pago_existente.id,
                'message': 'Ya existe una preferencia para este trabajo',
            })

        try:
            resultado = services.crear_preferencia_trabajo(trabajo, request)
            return Response(resultado, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.exception("Error creando preferencia para trabajo %s", trabajo_id)
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # ------------------------------------------------------------------
    # Tarjetas
    # ------------------------------------------------------------------

    @action(detail=False, methods=['get'], url_path='tarjetas')
    def listar_tarjetas(self, request):
        tarjetas = services.listar_tarjetas(request.user)
        serializer = TarjetaSerializer(tarjetas, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='guardar-tarjeta')
    def guardar_tarjeta(self, request):
        serializer = GuardarTarjetaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            tarjeta = services.guardar_tarjeta(
                request.user,
                serializer.validated_data['card_token'],
            )
            return Response(TarjetaSerializer(tarjeta).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.exception("Error guardando tarjeta")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['delete'], url_path=r'tarjetas/(?P<tarjeta_id>\d+)')
    def eliminar_tarjeta(self, request, tarjeta_id=None):
        exito = services.eliminar_tarjeta(request.user, int(tarjeta_id))
        if exito:
            return Response({'message': 'Tarjeta eliminada'})
        return Response({'error': 'Tarjeta no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    @action(detail=False, methods=['get'], url_path='medios-de-pago')
    def medios_de_pago(self, request):
        medios = services.obtener_medios_pago()
        return Response(medios)

    @action(detail=False, methods=['get'], url_path='cuotas')
    def cuotas(self, request):
        payment_method_id = request.query_params.get('payment_method_id', '')
        amount = request.query_params.get('amount', '0')
        issuer_id = request.query_params.get('issuer_id', '')

        if not payment_method_id or not amount:
            return Response(
                {'error': 'payment_method_id y amount requeridos'},
                status=status.HTTP_400_BAD_REQUEST
            )

        cuotas = services.obtener_cuotas(payment_method_id, float(amount), issuer_id)
        return Response(cuotas)

    @action(detail=False, methods=['get'], url_path='public-key')
    def public_key(self, request):
        """Devuelve la public key de MP para que el frontend inicialice el SDK."""
        from django.conf import settings
        return Response({'public_key': settings.MP_PUBLIC_KEY})

    # ------------------------------------------------------------------
    # Consultas por entidad
    # ------------------------------------------------------------------

    @action(detail=True, methods=['post'], url_path='reembolsar')
    def reembolsar(self, request, pk=None):
        pago = self.get_object()

        if pago.usuario != request.user:
            return Response(
                {'error': 'No tenés permisos para reembolsar este pago'},
                status=status.HTTP_403_FORBIDDEN
            )

        if pago.status not in ('aprobado',):
            return Response(
                {'error': f'No se puede reembolsar un pago en estado "{pago.status}"'},
                status=status.HTTP_400_BAD_REQUEST
            )

        exito = services.reembolsar_pago(pago)
        if exito:
            return Response({'message': 'Reembolso procesado', 'pago': PagoSerializer(pago).data})
        return Response(
            {'error': 'Error al procesar el reembolso en MercadoPago'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    @action(detail=False, methods=['get'], url_path='por-orden/(?P<orden_id>[^/.]+)')
    def por_orden(self, request, orden_id=None):
        pagos = Pago.objects.filter(orden_id=orden_id, tipo='orden')
        serializer = PagoResumenSerializer(pagos, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='por-trabajo/(?P<trabajo_id>[^/.]+)')
    def por_trabajo(self, request, trabajo_id=None):
        pagos = Pago.objects.filter(trabajo_id=trabajo_id, tipo='trabajo')
        serializer = PagoResumenSerializer(pagos, many=True)
        return Response(serializer.data)


def _verificar_firma_webhook(request):
    """
    Verifica la firma HMAC del webhook de MercadoPago.
    Retorna True si es válida o si no hay secret configurado (desarrollo).
    """
    import hashlib
    import hmac
    from django.conf import settings as django_settings

    secret = django_settings.MP_WEBHOOK_SECRET
    if not secret:
        return True

    x_signature = request.headers.get('X-Signature', '')
    x_request_id = request.headers.get('X-Request-Id', '')

    if not x_signature:
        return True

    parts = {}
    for part in x_signature.split(','):
        kv = part.strip().split('=', 1)
        if len(kv) == 2:
            parts[kv[0].strip()] = kv[1].strip()

    ts = parts.get('ts', '')
    v1 = parts.get('v1', '')

    if not ts or not v1:
        return True

    data_id = request.query_params.get('data.id', '').lower()

    manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"

    computed = hmac.new(
        secret.encode(), manifest.encode(), hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(computed, v1)


@api_view(['POST'])
@permission_classes([AllowAny])
def webhook_mercadopago(request):
    """Endpoint para recibir webhooks de MercadoPago. Sin autenticación."""
    try:
        if not _verificar_firma_webhook(request):
            logger.warning("Webhook MP con firma inválida rechazado")
            return Response(status=status.HTTP_403_FORBIDDEN)

        data = request.data if request.data else request.query_params.dict()
        logger.info("Webhook MP recibido: %s", data)

        query_type = request.query_params.get('type') or request.query_params.get('topic')
        query_id = request.query_params.get('data.id') or request.query_params.get('id')

        if query_type and query_id and not request.data:
            data = {
                "type": query_type,
                "data": {"id": query_id},
            }

        pago = services.procesar_webhook(data)
        if pago:
            logger.info("Pago %s actualizado a status=%s", pago.id, pago.status)
        return Response(status=status.HTTP_200_OK)
    except Exception:
        logger.exception("Error procesando webhook MP")
        return Response(status=status.HTTP_200_OK)
