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
        """Crea una orden a partir del carrito"""
        carrito = self.get_object()

        if not carrito.items.exists():
            return Response(
                {'error': 'El carrito está vacío'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = OrdenCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        tipo_entrega = serializer.validated_data['tipo_entrega']

        # Determinar la localización según el tipo de entrega
        if tipo_entrega == 'retiro':
            # Usar la localización de la empresa
            localizacion_entrega = carrito.empresa.localizacion
            if not localizacion_entrega:
                return Response(
                    {'error': 'La empresa no tiene localización configurada para retiro'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:  # domicilio
            # Usar la localización principal del usuario
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

        with transaction.atomic():
            total = carrito.total

            orden = Orden.objects.create(
                usuario=request.user,
                empresa=carrito.empresa,
                metodo_pago=serializer.validated_data['metodo_pago'],
                tipo_entrega=tipo_entrega,
                localizacion_entrega=localizacion_entrega,
                total=total,
                notas=serializer.validated_data.get('notas', '')
            )

            for item in carrito.items.all():
                if item.producto.agotado:
                    orden.delete()
                    return Response(
                        {'error': f'El producto "{item.producto.nombre}" está agotado'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                OrdenItem.objects.create(
                    orden=orden,
                    producto=item.producto,
                    cantidad=item.cantidad,
                    precio_unitario=item.precio_unitario,
                    subtotal=item.subtotal
                )

            carrito.activo = False
            carrito.save()

            # Crear notificación para el usuario
            Notificaciones.objects.create(
                usuario=request.user,
                titulo='Orden creada',
                descripcion=f'Tu orden #{orden.numero_orden} de {carrito.empresa.nombre} ha sido creada exitosamente. Total: ${orden.total}',
                deep_link=f'/ordenes/{orden.id}',
                entity_id=orden.id
            )

            # Crear notificación para el admin de la empresa
            if carrito.empresa.admin_id != request.user:
                Notificaciones.objects.create(
                    usuario=carrito.empresa.admin_id,
                    titulo='Nueva orden recibida',
                    descripcion=f'Nueva orden #{orden.numero_orden} de {request.user.nombre} {request.user.apellido}. Total: ${orden.total}',
                    deep_link=f'/ordenes/{orden.id}',
                    entity_id=orden.id
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

        # Mapeo de estados para mensajes más amigables
        estados_mensajes = {
            'en_proceso': 'está siendo procesada',
            'aceptada': 'ha sido aceptada',
            'entregada': 'ha sido entregada',
            'finalizada': 'ha sido finalizada',
            'cancelada': 'ha sido cancelada'
        }

        mensaje_estado = estados_mensajes.get(nuevo_estado, f'cambió a {orden.get_status_display()}')

        # Crear notificación para el cliente
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
