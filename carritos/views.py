import logging

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from django.db import transaction
from rest_framework import serializers as drf_serializers

from .models import Carrito, CarritoItem, Orden, OrdenItem
from .serializers import (
    CarritoSerializer, CarritoItemSerializer, CarritoItemCreateSerializer,
    OrdenSerializer, OrdenCreateSerializer
)
from empresas.models import Empresa, Producto
from notificaciones.models import Notificaciones

logger = logging.getLogger(__name__)


class CarritoViewSet(viewsets.ModelViewSet):
    serializer_class = CarritoSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return Carrito.objects.filter(
            usuario=self.request.user,
            activo=True
        ).select_related('empresa').prefetch_related('items__producto')

    @action(detail=False, methods=['get'], url_path='empresa/(?P<empresa_id>[^/.]+)')
    def por_empresa(self, request, empresa_id=None):
        """Obtiene o crea el carrito activo para una empresa específica"""
        try:
            empresa = Empresa.objects.get(id=empresa_id)
        except Empresa.DoesNotExist:
            return Response(
                {'error': 'Empresa no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )

        carrito, created = Carrito.objects.get_or_create(
            usuario=request.user,
            empresa=empresa,
            activo=True
        )

        serializer = self.get_serializer(carrito)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='agregar-item')
    def agregar_item(self, request, pk=None):
        """Agrega o actualiza un producto en el carrito"""
        carrito = self.get_object()
        serializer = CarritoItemCreateSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        producto_id = serializer.validated_data['producto_id']
        cantidad = serializer.validated_data['cantidad']

        try:
            producto = Producto.objects.get(id=producto_id, empresa=carrito.empresa)
        except Producto.DoesNotExist:
            return Response(
                {'error': 'Producto no encontrado en esta empresa'},
                status=status.HTTP_404_NOT_FOUND
            )

        if producto.agotado:
            return Response(
                {'error': 'Este producto está agotado'},
                status=status.HTTP_400_BAD_REQUEST
            )

        carrito_item, created = CarritoItem.objects.get_or_create(
            carrito=carrito,
            producto=producto,
            defaults={'cantidad': cantidad, 'precio_unitario': producto.precio}
        )

        if not created:
            carrito_item.cantidad += cantidad
            carrito_item.save()

        return Response(CarritoItemSerializer(carrito_item).data)

    @action(detail=True, methods=['post'], url_path='actualizar-item')
    def actualizar_item(self, request, pk=None):
        """Actualiza la cantidad de un item del carrito"""
        carrito = self.get_object()
        producto_id = request.data.get('producto_id')
        cantidad = request.data.get('cantidad')

        if not producto_id or cantidad is None:
            return Response(
                {'error': 'Se requiere producto_id y cantidad'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            carrito_item = CarritoItem.objects.get(carrito=carrito, producto_id=producto_id)
        except CarritoItem.DoesNotExist:
            return Response(
                {'error': 'Item no encontrado en el carrito'},
                status=status.HTTP_404_NOT_FOUND
            )

        if cantidad <= 0:
            carrito_item.delete()
            return Response({'message': 'Item eliminado del carrito'})

        carrito_item.cantidad = cantidad
        carrito_item.save()

        return Response(CarritoItemSerializer(carrito_item).data)

    @action(detail=True, methods=['delete'], url_path='eliminar-item/(?P<producto_id>[^/.]+)')
    def eliminar_item(self, request, pk=None, producto_id=None):
        """Elimina un producto del carrito"""
        carrito = self.get_object()

        try:
            carrito_item = CarritoItem.objects.get(carrito=carrito, producto_id=producto_id)
            carrito_item.delete()
            return Response({'message': 'Item eliminado del carrito'})
        except CarritoItem.DoesNotExist:
            return Response(
                {'error': 'Item no encontrado en el carrito'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['delete'], url_path='vaciar')
    def vaciar(self, request, pk=None):
        """Vacía el carrito eliminando todos los items"""
        carrito = self.get_object()
        carrito.items.all().delete()
        return Response({'message': 'Carrito vaciado exitosamente'})

    @action(detail=True, methods=['post'], url_path='checkout')
    def checkout(self, request, pk=None):
        """
        Crea una orden a partir del carrito.
        Para mercadopago: procesa el pago PRIMERO; la orden solo se crea si
        el cobro es exitoso, evitando órdenes huérfanas.
        """
        carrito = self.get_object()

        if not carrito.items.exists():
            return Response(
                {'error': 'El carrito está vacío'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = OrdenCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        metodo_pago = serializer.validated_data['metodo_pago']
        empresa = carrito.empresa

        if metodo_pago == 'mercadopago' and not empresa.acepta_tarjeta:
            return Response(
                {'error': 'Esta empresa no acepta pagos con tarjeta'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if metodo_pago == 'efectivo':
            if not empresa.acepta_efectivo:
                return Response(
                    {'error': 'Esta empresa no acepta pagos en efectivo'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            from suscripciones.models import Subscripcion
            from django.utils import timezone as tz
            tiene_sub = Subscripcion.objects.filter(
                user_id=empresa.admin_id,
                cancelada=False,
                expiracion__gt=tz.now(),
            ).exists()
            if not tiene_sub:
                return Response(
                    {'error': 'La empresa necesita una suscripción activa para aceptar efectivo'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        tipo_entrega = serializer.validated_data['tipo_entrega']
        if tipo_entrega == 'retiro':
            localizacion_entrega = carrito.empresa.localizacion
            if not localizacion_entrega:
                return Response(
                    {'error': 'La empresa no tiene localización configurada para retiro'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            from usuario_localizacion.models import UsuarioLocalizacion
            try:
                usuario_loc = UsuarioLocalizacion.objects.get(
                    usuario=request.user,
                    es_principal=True
                )
                localizacion_entrega = usuario_loc.localizacion
            except UsuarioLocalizacion.DoesNotExist:
                return Response(
                    {'error': 'No tienes una dirección principal configurada para envío a domicilio'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Validar stock antes de cualquier cobro
        items_carrito = list(carrito.items.select_related('producto').all())
        for item in items_carrito:
            if item.producto.agotado:
                return Response(
                    {'error': f'El producto "{item.producto.nombre}" está agotado'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        total = carrito.total

        # ── MercadoPago: cobrar ANTES de crear la orden ──────────────
        mp_response = None
        if metodo_pago == 'mercadopago':
            from pagos.services import ejecutar_pago_mp, calcular_comision
            from pagos.models import MercadoPagoCustomer

            mp_customer_id = ''
            try:
                mp_cust = MercadoPagoCustomer.objects.get(usuario=request.user)
                mp_customer_id = mp_cust.mp_customer_id
            except MercadoPagoCustomer.DoesNotExist:
                pass

            try:
                mp_response = ejecutar_pago_mp(
                    email=request.user.correo,
                    monto=total,
                    card_token=serializer.validated_data['card_token'],
                    payment_method_id=serializer.validated_data.get('payment_method_id', ''),
                    issuer_id=serializer.validated_data.get('issuer_id', ''),
                    installments=serializer.validated_data.get('installments', 1),
                    descripcion=f"Orden en {empresa.nombre}",
                    external_ref=f"carrito_{carrito.id}",
                    bin_tarjeta=serializer.validated_data.get('bin', ''),
                    mp_customer_id=mp_customer_id,
                    payment_method_type=serializer.validated_data.get('payment_method_type', ''),
                )
            except Exception as e:
                logger.exception("Pago MP rechazado para carrito %s", carrito.id)
                return Response(
                    {'error': f'El pago fue rechazado: {e}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # ── Pago OK (o efectivo): crear orden + registros en una TX ──
        with transaction.atomic():
            comision_plataforma = None
            pago_status = ''
            if metodo_pago == 'mercadopago':
                comision_plataforma, _ = calcular_comision(total)
                pago_status = 'aprobado'

            orden = Orden.objects.create(
                usuario=request.user,
                empresa=empresa,
                metodo_pago=metodo_pago,
                tipo_entrega=tipo_entrega,
                localizacion_entrega=localizacion_entrega,
                total=total,
                notas=serializer.validated_data.get('notas', ''),
                comision_plataforma=comision_plataforma,
                pago_status=pago_status,
            )

            for item in items_carrito:
                OrdenItem.objects.create(
                    orden=orden,
                    producto=item.producto,
                    cantidad=item.cantidad,
                    precio_unitario=item.precio_unitario,
                    subtotal=item.subtotal,
                )

            # Registrar el Pago si fue mercadopago (Orders API response)
            if mp_response:
                from pagos.models import Pago
                from pagos.services import ORDERS_STATUS_MAP
                comision, monto_vendedor = calcular_comision(total)
                order_status = mp_response.get("status", "")
                payments = mp_response.get("transactions", {}).get("payments", [])
                mp_payment_id = str(payments[0].get("id", "")) if payments else ""
                Pago.objects.create(
                    tipo='orden',
                    orden=orden,
                    usuario=request.user,
                    monto=total,
                    comision_plataforma=comision,
                    monto_vendedor=monto_vendedor,
                    mp_order_id=str(mp_response.get("id", "")),
                    mp_payment_id=mp_payment_id,
                    mp_status=order_status,
                    mp_status_detail=mp_response.get("status_detail", ""),
                    status=ORDERS_STATUS_MAP.get(order_status, 'pendiente'),
                )

            carrito.activo = False
            carrito.save()

            Notificaciones.objects.create(
                usuario=request.user,
                titulo='Orden creada',
                descripcion=f'Tu orden #{orden.numero_orden} de {empresa.nombre} ha sido creada exitosamente. Total: ${orden.total}',
                deep_link=f'/ordenes/{orden.id}',
                entity_id=orden.id,
            )

            if empresa.admin_id != request.user:
                Notificaciones.objects.create(
                    usuario=empresa.admin_id,
                    titulo='Nueva orden recibida',
                    descripcion=f'Nueva orden #{orden.numero_orden} de {request.user.nombre} {request.user.apellido}. Total: ${orden.total}',
                    deep_link=f'/ordenes/{orden.id}',
                    entity_id=orden.id,
                )

        return Response(OrdenSerializer(orden).data, status=status.HTTP_201_CREATED)


class OrdenViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrdenSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        from django.db.models import Q
        
        queryset = Orden.objects.filter(
            Q(usuario=self.request.user) | Q(empresa__admin_id=self.request.user)
        ).distinct()
        
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        empresa_id = self.request.query_params.get('empresa_id', None)
        if empresa_id:
            queryset = queryset.filter(empresa_id=empresa_id)
        
        return queryset.select_related('empresa', 'usuario').prefetch_related('items__producto')

    @action(detail=True, methods=['post'], url_path='cambiar-estado')
    def cambiar_estado(self, request, pk=None):
        """Cambia el estado de una orden (solo para admin de empresa)"""
        orden = self.get_object()
        nuevo_estado = request.data.get('status')

        if nuevo_estado not in dict(Orden.STATUS_CHOICES):
            return Response(
                {'error': 'Estado inválido'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if orden.empresa.admin_id != request.user:
            return Response(
                {'error': 'No tienes permisos para cambiar el estado de esta orden'},
                status=status.HTTP_403_FORBIDDEN
            )

        estado_anterior = orden.get_status_display()
        orden.status = nuevo_estado
        orden.save()

        if nuevo_estado == 'finalizada' and orden.metodo_pago == 'mercadopago':
            try:
                from pagos.services import liberar_pagos_entidad
                liberados = liberar_pagos_entidad('orden', orden.id)
                if liberados > 0:
                    orden.pago_status = 'liberado'
                    orden.save(update_fields=['pago_status'])
                    logger.info("Liberados %d pagos para orden %s", liberados, orden.id)
            except Exception as e:
                logger.exception("Error liberando pagos para orden %s", orden.id)

        if nuevo_estado == 'cancelada' and orden.metodo_pago == 'mercadopago':
            try:
                from pagos.models import Pago
                from pagos.services import reembolsar_pago
                pagos_aprobados = Pago.objects.filter(
                    orden=orden, tipo='orden', status='aprobado'
                )
                for pago in pagos_aprobados:
                    reembolsar_pago(pago)
                orden.pago_status = 'devuelto'
                orden.save(update_fields=['pago_status'])
            except Exception as e:
                logger.exception("Error reembolsando pagos para orden %s", orden.id)

        estados_mensajes = {
            'en_proceso': 'está siendo procesada',
            'aceptada': 'ha sido aceptada',
            'entregada': 'ha sido entregada',
            'finalizada': 'ha sido finalizada',
            'cancelada': 'ha sido cancelada'
        }

        mensaje_estado = estados_mensajes.get(nuevo_estado, f'cambió a {orden.get_status_display()}')

        Notificaciones.objects.create(
            usuario=orden.usuario,
            titulo=f'Orden {orden.get_status_display()}',
            descripcion=f'Tu orden #{orden.numero_orden} de {orden.empresa.nombre} {mensaje_estado}.',
            deep_link=f'/ordenes/{orden.id}',
            entity_id=orden.id
        )

        return Response(OrdenSerializer(orden).data)

    @action(detail=False, methods=['get'], url_path='mis-ordenes-empresa')
    def mis_ordenes_empresa(self, request):
        """Listado de órdenes para empresas que administra el usuario"""
        empresas = Empresa.objects.filter(admin_id=request.user)
        queryset = Orden.objects.filter(empresa__in=empresas)
        
        status_filter = request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        queryset = queryset.select_related('empresa', 'usuario').prefetch_related('items__producto')
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
