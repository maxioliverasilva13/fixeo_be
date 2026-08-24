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
from whatsapp.tasks import enviar_mensaje_whatsapp_task
from django.db.models import Q
from django.utils import timezone
from .chat_helpers import enviar_mensaje_orden_chat

logger = logging.getLogger(__name__)

TIPO_ENTREGA_TEXTOS = {
    'retiro': 'Retiro en local',
    'domicilio': 'Envío a domicilio',
}

DIA_SEMANA_NOMBRES = {
    1: 'lunes', 2: 'martes', 3: 'miércoles', 4: 'jueves',
    5: 'viernes', 6: 'sábado', 7: 'domingo',
}


def _producto_disponible_en_fecha(producto, fecha):
    """True si el plato de menú tiene ese día de semana activo."""
    if not getattr(producto, 'es_menu_diario', False):
        return True
    dia = fecha.isoweekday()  # 1=lun … 7=dom
    return producto.dias_menu.filter(
        dia_semana=dia, activo=True, is_deleted=False,
    ).exists()


def _clear_fecha_menu_si_vacio(carrito):
    if not carrito.items.filter(is_deleted=False).exists():
        if carrito.fecha_menu is not None:
            carrito.fecha_menu = None
            carrito.save(update_fields=['fecha_menu', 'updated_at'])


def _detalle_productos_orden(orden):
    """Ej: '2x Corte de cabello, 1x Shampoo'"""
    items = list(orden.items.select_related('producto').all())
    if not items:
        return ''
    return ', '.join(f"{item.cantidad}x {item.producto.nombre}" for item in items)


def _total_formateado(orden):
    moneda = f" {orden.currency}" if orden.currency else ''
    return f"${orden.total}{moneda}"


def _direccion_orden(orden):
    """
    Dirección relevante según el tipo de entrega: si es retiro, la del local
    del profesional; si es a domicilio, la del usuario. Ambos casos ya
    quedan resueltos en orden.localizacion_entrega al crear la orden.
    """
    loc = orden.localizacion_entrega
    if not loc:
        return ''
    direccion = loc.address or loc.ubicacion
    if loc.city:
        direccion = f"{direccion}, {loc.city}" if direccion else loc.city
    if not direccion:
        return ''
    etiqueta = 'Dirección de retiro' if orden.tipo_entrega == 'retiro' else 'Dirección de entrega'
    return f"{etiqueta}: {direccion}"


def _mensaje_whatsapp_orden(orden, encabezado, motivo=None):
    """
    Arma un mensaje de WhatsApp con el detalle de la orden: producto/s,
    total, tipo de entrega, dirección, fecha/hora del evento, notas y
    motivo (si aplica). El encabezado ya debe traer resaltado con *...* lo
    importante (nro. de orden, nuevo estado).
    """
    lineas = [encabezado]

    detalle = _detalle_productos_orden(orden)
    if detalle:
        lineas.append(f"  Producto/s: {detalle}")

    lineas.append(f"  Total: *{_total_formateado(orden)}*")
    lineas.append(f"  Entrega: {TIPO_ENTREGA_TEXTOS.get(orden.tipo_entrega, orden.tipo_entrega)}")

    direccion = _direccion_orden(orden)
    if direccion:
        lineas.append(f"  {direccion}")

    ahora = timezone.localtime(timezone.now())
    lineas.append(f"  Fecha: *{ahora.strftime('%d/%m/%Y')}*")
    lineas.append(f"  Hora: *{ahora.strftime('%H:%M')}*")

    if orden.notas:
        lineas.append(f"  Notas: {orden.notas}")

    if motivo:
        lineas.append(f"  Motivo: *{motivo}*")

    return '\n'.join(lineas)


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
        variante_id = serializer.validated_data.get('variante_id')
        fecha_menu = serializer.validated_data.get('fecha_menu')

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

        items_existentes = list(
            carrito.items.select_related('producto').filter(is_deleted=False)
        )
        hay_menu = any(getattr(i.producto, 'es_menu_diario', False) for i in items_existentes)
        hay_retail = any(not getattr(i.producto, 'es_menu_diario', False) for i in items_existentes)

        if producto.es_menu_diario and hay_retail:
            return Response(
                {'error': 'No podés mezclar menú diario con otros productos en el mismo carrito'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not producto.es_menu_diario and (hay_menu or carrito.fecha_menu):
            return Response(
                {'error': 'Este carrito es de menú diario. Vacialo para agregar otros productos'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if producto.es_menu_diario:
            today = timezone.localdate()
            target_fecha = fecha_menu or carrito.fecha_menu
            if not target_fecha:
                return Response(
                    {'error': 'Elegí la fecha del menú para agregar este plato'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if target_fecha < today:
                return Response(
                    {'error': 'La fecha del menú no puede ser en el pasado'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if carrito.fecha_menu and carrito.fecha_menu != target_fecha:
                return Response(
                    {
                        'error': (
                            f'Este carrito es para el {carrito.fecha_menu.strftime("%d/%m/%Y")}. '
                            'Vacialo para pedir otro día'
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not _producto_disponible_en_fecha(producto, target_fecha):
                dia_nombre = DIA_SEMANA_NOMBRES.get(target_fecha.isoweekday(), 'ese día')
                return Response(
                    {'error': f'"{producto.nombre}" no está disponible los {dia_nombre}'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if carrito.fecha_menu is None:
                carrito.fecha_menu = target_fecha
                carrito.save(update_fields=['fecha_menu', 'updated_at'])

        variante = None
        precio_extra = 0
        if variante_id:
            from empresas.models import ProductoVariante
            variante = ProductoVariante.objects.filter(
                id=variante_id, producto=producto, activo=True, is_deleted=False,
            ).first()
            if not variante:
                return Response(
                    {'error': 'Variante no encontrada'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            precio_extra = variante.precio_extra or 0

        precio_unitario = producto.precio + precio_extra

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
            variante=variante,
        ).first()

        if carrito_item:
            if carrito_item.is_deleted:
                carrito_item.is_deleted = False
                carrito_item.deleted_at = None
                carrito_item.deleted_by = None
                carrito_item.cantidad = cantidad
                carrito_item.precio_unitario = precio_unitario
                carrito_item.variante = variante
                carrito_item.save()
            else:
                carrito_item.cantidad += cantidad
                carrito_item.precio_unitario = precio_unitario
                carrito_item.save()
        else:
            carrito_item = CarritoItem.objects.create(
                carrito=carrito,
                producto=producto,
                variante=variante,
                cantidad=cantidad,
                precio_unitario=precio_unitario,
            )

        return Response(CarritoItemSerializer(carrito_item).data)

    @action(detail=True, methods=['post'], url_path='actualizar-item')
    def actualizar_item(self, request, pk=None):
        """Actualiza la cantidad de un item del carrito"""
        carrito = self.get_object()
        producto_id = request.data.get('producto_id')
        cantidad = request.data.get('cantidad')
        variante_id = request.data.get('variante_id')

        if not producto_id or cantidad is None:
            return Response(
                {'error': 'Se requiere producto_id y cantidad'},
                status=status.HTTP_400_BAD_REQUEST
            )

        qs = CarritoItem.objects.filter(carrito=carrito, producto_id=producto_id)
        if variante_id:
            qs = qs.filter(variante_id=variante_id)
        else:
            qs = qs.filter(variante__isnull=True)

        carrito_item = qs.first()
        if not carrito_item:
            return Response(
                {'error': 'Item no encontrado en el carrito'},
                status=status.HTTP_404_NOT_FOUND
            )

        if cantidad <= 0:
            carrito_item.delete()
            _clear_fecha_menu_si_vacio(carrito)
            return Response({'message': 'Item eliminado del carrito'})

        carrito_item.cantidad = cantidad
        carrito_item.save()

        return Response(CarritoItemSerializer(carrito_item).data)

    @action(detail=True, methods=['delete'], url_path='eliminar-item/(?P<producto_id>[^/.]+)')
    def eliminar_item(self, request, pk=None, producto_id=None):
        """Elimina un producto del carrito. Opcional: ?variante_id= """
        carrito = self.get_object()
        variante_id = request.query_params.get('variante_id')

        qs = CarritoItem.objects.filter(carrito=carrito, producto_id=producto_id)
        if variante_id:
            qs = qs.filter(variante_id=variante_id)
        else:
            qs = qs.filter(variante__isnull=True)

        carrito_item = qs.first()
        if not carrito_item:
            return Response(
                {'error': 'Item no encontrado en el carrito'},
                status=status.HTTP_404_NOT_FOUND
            )
        carrito_item.delete()
        _clear_fecha_menu_si_vacio(carrito)
        return Response({'message': 'Item eliminado del carrito'})

    @action(detail=True, methods=['delete'], url_path='vaciar')
    def vaciar(self, request, pk=None):
        """Vacía el carrito eliminando todos los items"""
        carrito = self.get_object()
        carrito.items.all().delete()
        carrito.fecha_menu = None
        carrito.save(update_fields=['fecha_menu', 'updated_at'])
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

        items_carrito = list(carrito.items.select_related('producto', 'variante').all())
        es_menu_diario = any(getattr(item.producto, 'es_menu_diario', False) for item in items_carrito)

        if es_menu_diario:
            if not carrito.fecha_menu:
                return Response(
                    {'error': 'Este pedido de menú no tiene fecha. Volvé a armar el carrito'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if carrito.fecha_menu < timezone.localdate():
                return Response(
                    {'error': 'La fecha del menú ya pasó. Elegí otra fecha'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            for item in items_carrito:
                if not _producto_disponible_en_fecha(item.producto, carrito.fecha_menu):
                    return Response(
                        {
                            'error': (
                                f'"{item.producto.nombre}" no está disponible '
                                f'el {carrito.fecha_menu.strftime("%d/%m/%Y")}'
                            ),
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        if metodo_pago == 'transferencia':
            if not es_menu_diario or not empresa.vende_menu_diario:
                return Response(
                    {'error': 'Transferencia solo está disponible para pedidos de menú diario'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

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

            if (
                localizacion_entrega.latitud is not None
                and localizacion_entrega.longitud is not None
            ):
                from usuario.zonas_utils import (
                    mensaje_zona_no_atendida,
                    ubicacion_bloqueada_por_zonas_profesional,
                )
                if ubicacion_bloqueada_por_zonas_profesional(
                    empresa.admin_id,
                    localizacion_entrega.latitud,
                    localizacion_entrega.longitud,
                ):
                    return Response(
                        {'error': mensaje_zona_no_atendida()},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        # Validar stock antes de cualquier cobro
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

        # ── Pago OK (o efectivo/transferencia): crear orden + registros en una TX ──
        with transaction.atomic():
            comision_plataforma = None
            pago_status = ''
            if metodo_pago == 'mercadopago':
                comision_plataforma, _ = calcular_comision(total)
                pago_status = 'aprobado'
            elif metodo_pago == 'transferencia':
                pago_status = 'pendiente'
            elif metodo_pago == 'efectivo':
                pago_status = (
                    'pago_en_domicilio' if tipo_entrega == 'domicilio' else 'pendiente'
                )

            from datetime import datetime, time as time_cls
            from django.utils import timezone as dj_tz

            fecha_entrega = None
            if es_menu_diario and carrito.fecha_menu:
                # Mediodía local del día elegido (DateTimeField en Orden)
                naive = datetime.combine(carrito.fecha_menu, time_cls(12, 0))
                fecha_entrega = dj_tz.make_aware(naive, dj_tz.get_current_timezone())

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
                fecha_entrega=fecha_entrega,
            )

            for item in items_carrito:
                OrdenItem.objects.create(
                    orden=orden,
                    producto=item.producto,
                    cantidad=item.cantidad,
                    precio_unitario=item.precio_unitario,
                    subtotal=item.subtotal,
                    variante_nombre=(item.variante.nombre if item.variante_id else ''),
                    variante_precio_extra=(
                        item.variante.precio_extra if item.variante_id else 0
                    ),
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

            logger.info(
                "Encolando WhatsApp de orden creada para orden %s (usuario_id=%s), se disparará on_commit",
                orden.id, request.user.id,
            )

            def _enviar_whatsapp_orden_creada():
                logger.info(
                    "Disparando WhatsApp de orden creada (orden_id=%s, usuario_id=%s)",
                    orden.id, request.user.id,
                )
                enviar_mensaje_whatsapp_task.delay(
                    usuario_id=request.user.id,
                    body=_mensaje_whatsapp_orden(
                        orden,
                        encabezado=(
                            f'Tu orden *#{orden.numero_orden}* en {empresa.nombre} *fue registrada*.\n'
                            f'Está *pendiente de confirmación* del profesional. '
                            f'Te vamos a avisar por acá apenas la acepte.'
                        ),
                    ),
                    profesional_id=empresa.admin_id_id,
                )

            transaction.on_commit(_enviar_whatsapp_orden_creada)

            if empresa.admin_id_id != request.user.id:
                cliente_nombre = (
                    f"{request.user.nombre} {request.user.apellido}".strip()
                    or request.user.correo
                )
                cantidad_items = sum(item.cantidad for item in items_carrito)
                metodo_display = {
                    'efectivo': 'efectivo',
                    'transferencia': 'transferencia',
                    'mercadopago': 'MercadoPago',
                }.get(metodo_pago, metodo_pago)
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

        motivo = (request.data.get('motivo') or '').strip()
        if nuevo_estado == 'cancelada' and not motivo:
            return Response(
                {'error': 'Debes indicar un motivo para cancelar la orden'},
                status=status.HTTP_400_BAD_REQUEST
            )

        estado_anterior = orden.get_status_display()
        orden.status = nuevo_estado
        if nuevo_estado == 'cancelada':
            orden.motivo_cancelacion = motivo
            orden.save(update_fields=['status', 'motivo_cancelacion', 'updated_at'])
        else:
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

        encabezado_whatsapp = (
            f'Tu orden *#{orden.numero_orden}* de {orden.empresa.nombre} *{mensaje_estado}*.'
        )
        texto_whatsapp = _mensaje_whatsapp_orden(
            orden,
            encabezado=encabezado_whatsapp,
            motivo=motivo if nuevo_estado == 'cancelada' else None,
        )

        logger.info(
            "Encolando WhatsApp de cambio de estado para orden %s (usuario_id=%s, %s -> %s)",
            orden.id, orden.usuario_id, estado_anterior, nuevo_estado,
        )
        enviar_mensaje_whatsapp_task.delay(
            usuario_id=orden.usuario_id,
            body=texto_whatsapp,
            profesional_id=orden.empresa.admin_id_id,
        )

        enviar_mensaje_orden_chat(
            orden,
            texto=texto_estado,
            sender=request.user,
            receiver=orden.usuario,
            tipo='orden_estado',
        )

        return Response(OrdenSerializer(orden, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='marcar-pagado')
    def marcar_pagado(self, request, pk=None):
        """Marca el pago como recibido (efectivo/transferencia). Foto de comprobante opcional."""
        orden = self.get_object()

        if orden.empresa.admin_id_id != request.user.id:
            return Response(
                {'error': 'No tienes permisos para marcar el pago de esta orden'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if orden.metodo_pago not in ('efectivo', 'transferencia'):
            return Response(
                {'error': 'Solo aplica a órdenes en efectivo o transferencia'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if orden.status == 'cancelada':
            return Response(
                {'error': 'No se puede marcar el pago de una orden cancelada'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if orden.pago_status == 'pagado':
            return Response(
                OrdenSerializer(orden, context={'request': request}).data,
            )

        comprobante = (request.data.get('comprobante_pago_url') or '').strip()
        orden.pago_status = 'pagado'
        update_fields = ['pago_status', 'updated_at']
        if comprobante:
            orden.comprobante_pago_url = comprobante[:500]
            update_fields.append('comprobante_pago_url')
        orden.save(update_fields=update_fields)

        Notificaciones.objects.create(
            usuario=orden.usuario,
            titulo='Pago confirmado',
            descripcion=(
                f'Tu pago de la orden #{orden.numero_orden} en {orden.empresa.nombre} '
                f'fue marcado como recibido.'
            ),
            deep_link=f'/historial?ordenId={orden.id}',
            entity_id=orden.id,
        )

        enviar_mensaje_orden_chat(
            orden,
            texto=f'Tu pago de la orden #{orden.numero_orden} fue confirmado.',
            sender=request.user,
            receiver=orden.usuario,
            tipo='orden_pago',
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

        fecha_desde = request.query_params.get('fecha_desde')
        fecha_hasta = request.query_params.get('fecha_hasta')
        if fecha_desde:
            queryset = queryset.filter(created_at__date__gte=fecha_desde)
        if fecha_hasta:
            queryset = queryset.filter(created_at__date__lte=fecha_hasta)
        
        queryset = queryset.select_related('empresa', 'usuario').prefetch_related('items__producto')
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='contador-pendientes')
    def contador_pendientes(self, request):
        """
        Órdenes en estado inicial (UI "Pendientes"):
        - como_cliente: compras tuyas en_proceso
        - como_empresa: pedidos recibidos en tu negocio en_proceso
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

    @action(detail=False, methods=['get'], url_path='contador-activas')
    def contador_activas(self, request):
        """
        Órdenes no finalizadas ni canceladas:
        - como_cliente / como_empresa / total
        Incluye en_proceso, aceptada y entregada.
        """
        user = request.user
        activos = ~Q(status__in=['finalizada', 'cancelada'])
        como_cliente = Orden.objects.filter(usuario=user).filter(activos).count()
        empresas = Empresa.objects.filter(admin_id=user)
        como_empresa = (
            Orden.objects.filter(empresa__in=empresas).filter(activos).count()
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

    @action(detail=False, methods=['get'], url_path='contador-por-estado')
    def contador_por_estado(self, request):
        """
        Conteo de órdenes por estado, separado por rol.
        `activas` = en_proceso + aceptada + entregada.
        """
        from django.db.models import Count

        user = request.user
        estados = ['en_proceso', 'aceptada', 'entregada', 'finalizada', 'cancelada']

        def _por_estado(qs):
            raw = {
                row['status']: row['c']
                for row in qs.values('status').annotate(c=Count('id'))
            }
            en_proceso = raw.get('en_proceso', 0)
            aceptada = raw.get('aceptada', 0)
            entregada = raw.get('entregada', 0)
            return {
                'en_proceso': en_proceso,
                'aceptada': aceptada,
                'entregada': entregada,
                'finalizada': raw.get('finalizada', 0),
                'cancelada': raw.get('cancelada', 0),
                'activas': en_proceso + aceptada + entregada,
            }

        como_cliente = _por_estado(Orden.objects.filter(usuario=user, status__in=estados))
        empresas = Empresa.objects.filter(admin_id=user)
        como_empresa = (
            _por_estado(Orden.objects.filter(empresa__in=empresas, status__in=estados))
            if empresas.exists()
            else {
                'en_proceso': 0,
                'aceptada': 0,
                'entregada': 0,
                'finalizada': 0,
                'cancelada': 0,
                'activas': 0,
            }
        )
        return Response(
            {
                'como_cliente': como_cliente,
                'como_empresa': como_empresa,
            },
            status=status.HTTP_200_OK,
        )
