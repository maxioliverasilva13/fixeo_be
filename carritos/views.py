import logging
from django.db import IntegrityError, transaction
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from django.db import transaction
from rest_framework import serializers as drf_serializers
from mensajeria.models import Chat, Mensajes
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Carrito, CarritoItem, Orden, OrdenItem
from .serializers import (
    CarritoSerializer, CarritoItemSerializer, CarritoItemCreateSerializer,
    OrdenSerializer, OrdenCreateSerializer
)
from empresas.models import Empresa, Producto
from empresas.delivery_utils import productos_comparten_modalidad, validar_tipo_entrega_productos
from notificaciones.models import Notificaciones
from notificaciones.tasks import notificar_usuario
from django.db.models import Q
from .chat_helpers import enviar_mensaje_orden_chat

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

        existing_productos = list(
            Producto.objects.filter(carritoitem__carrito=carrito, carritoitem__is_deleted=False)
            .exclude(id=producto_id)
            .distinct()
        )
        compatible, _, _ = productos_comparten_modalidad(existing_productos + [producto])
        if existing_productos and not compatible:
            return Response(
                {'error': 'Este producto no se puede combinar con los del carrito (modalidad de entrega incompatible)'},
                status=status.HTTP_400_BAD_REQUEST
            )

        carrito_item = CarritoItem.all_objects.filter(
            carrito=carrito,
            producto=producto,
        ).first()

        if carrito_item:
            if carrito_item.is_deleted:
                carrito_item.is_deleted = False
                carrito_item.deleted_at = None
                carrito_item.deleted_by = None
                carrito_item.cantidad = cantidad
                carrito_item.precio_unitario = producto.precio
                carrito_item.save()
            else:
                carrito_item.cantidad += cantidad
                carrito_item.save()
        else:
            carrito_item = CarritoItem.objects.create(
                carrito=carrito,
                producto=producto,
                cantidad=cantidad,
                precio_unitario=producto.precio,
            )

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

        items_carrito = list(carrito.items.select_related('producto').all())
        entrega_error = validar_tipo_entrega_productos(
            [item.producto for item in items_carrito],
            tipo_entrega,
        )
        if entrega_error:
            return Response({'error': entrega_error}, status=status.HTTP_400_BAD_REQUEST)

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

        divisas_en_carrito = {
            getattr(item.producto, 'divisa', None) or 'USD'
            for item in items_carrito
        }
        if len(divisas_en_carrito) > 1:
            return Response(
                {'error': 'No podés finalizar la compra con productos en distintas monedas. Ajustá tu carrito.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        orden_currency = next(iter(divisas_en_carrito), empresa.moneda_local)

        total = carrito.total
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
                currency=orden_currency,
            )

            for item in items_carrito:
                OrdenItem.objects.create(
                    orden=orden,
                    producto=item.producto,
                    cantidad=item.cantidad,
                    precio_unitario=item.precio_unitario,
                    subtotal=item.subtotal,
                )

            if mp_response:
                from pagos.models import Pago
                from pagos.services import MP_STATUS_MAP
                comision, monto_vendedor = calcular_comision(total)
                mp_status = mp_response.get("status", "")
                mp_payment_id = str(mp_response.get("id", ""))
                Pago.objects.create(
                    tipo='orden',
                    orden=orden,
                    usuario=request.user,
                    monto=total,
                    comision_plataforma=comision,
                    monto_vendedor=monto_vendedor,
                    mp_payment_id=mp_payment_id,
                    mp_status=mp_status,
                    mp_status_detail=mp_response.get("status_detail", ""),
                    status=MP_STATUS_MAP.get(mp_status, 'pendiente'),
                )

            carrito.activo = False
            carrito.save()

            texto_chat = (
                empresa.admin_id.defaultMessageReservation
                or f'Tu pedido #{orden.numero_orden} en {empresa.nombre} fue registrado. Total: ${orden.total}'
            )
            enviar_mensaje_orden_chat(
                orden,
                texto=texto_chat,
                sender=empresa.admin_id,
                receiver=request.user,
                tipo='orden_creada',
            )

            Notificaciones.objects.create(
                usuario=request.user,
                titulo='Orden creada',
                descripcion=f'Tu orden #{orden.numero_orden} de {empresa.nombre} ha sido creada exitosamente. Total: ${orden.total}',
                deep_link=f'/historial?ordenId={orden.id}',
                entity_id=orden.id,
            )

            if empresa.admin_id_id != request.user.id:
                cliente_nombre = (
                    f"{request.user.nombre} {request.user.apellido}".strip()
                    or request.user.correo
                )
                cantidad_items = sum(item.cantidad for item in items_carrito)
                metodo_display = 'efectivo' if metodo_pago == 'efectivo' else 'MercadoPago'
                total_str = f"${total}"
                productos_txt = (
                    f"{cantidad_items} producto"
                    if cantidad_items == 1
                    else f"{cantidad_items} productos"
                )
                push_titulo = f"Nueva orden · {total_str}"
                push_mensaje = (
                    f"{cliente_nombre} realizó un pedido por {total_str} "
                    f"({productos_txt}, pago en {metodo_display})."
                )
                push_data = {
                    'deep_link': f'/servicios?tab=ordenes&ordenId={orden.id}',
                    'entity_id': orden.id,
                    'orden_id': orden.id,
                    'tipo': 'nueva_orden',
                    'total': str(total),
                    'metodo_pago': metodo_pago,
                    'numero_orden': orden.numero_orden,
                }

                def enviar_push_vendedor():
                    notificar_usuario.delay(
                        usuario_id=empresa.admin_id_id,
                        titulo=push_titulo,
                        mensaje=push_mensaje,
                        data=push_data,
                    )

                transaction.on_commit(enviar_push_vendedor)

        return Response(
            OrdenSerializer(orden, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


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
            deep_link=f'/historial?ordenId={orden.id}',
            entity_id=orden.id,
        )

        texto_estado = (
            f'Tu orden #{orden.numero_orden} de {orden.empresa.nombre} {mensaje_estado}.'
        )
        enviar_mensaje_orden_chat(
            orden,
            texto=texto_estado,
            sender=request.user,
            receiver=orden.usuario,
            tipo='orden_estado',
        )

        return Response(OrdenSerializer(orden, context={'request': request}).data)

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

    @action(detail=False, methods=['get'], url_path='contador-pendientes')
    def contador_pendientes(self, request):
        """
        Órdenes en estado inicial (equivalente UI "pendientes" de productos):
        - como_cliente: compras tuyas en_proceso
        - como_empresa: pedidos recibidos en tu negocio (admin empresa) en_proceso
        - total: suma de ambos
        """
        user = request.user
        como_cliente = Orden.objects.filter(usuario=user, status='en_proceso').count()
        empresas = Empresa.objects.filter(admin_id=user)
        como_empresa = (
            Orden.objects.filter(empresa__in=empresas, status='en_proceso').count()
            if empresas.exists()
            else 0
        )
        return Response(
            {
                'como_cliente': como_cliente,
                'como_empresa': como_empresa,
                'total': como_cliente + como_empresa,
            },
            status=status.HTTP_200_OK,
        )
