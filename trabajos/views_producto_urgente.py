from datetime import timedelta

from django.db import connection, transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from empresas.models import Empresa
from localizacion.models import Localizacion
from localizacion.utils import calcular_distancia_km
from notificaciones.tasks import notificar_usuario, notificar_usuarios_multiple
from usuario.zonas_utils import filtrar_profesionales_fuera_zonas_exclusion
from usuario_localizacion.models import UsuarioLocalizacion

from .models import AlertaProductoUrgente, AlertaProductoFoto, RespuestaAlertaProducto
from .serializers_producto_urgente import (
    AlertaProductoUrgenteCreateSerializer,
    AlertaProductoUrgenteDetailSerializer,
    RespuestaAlertaProductoCreateSerializer,
    RespuestaAlertaProductoSerializer,
)

DEFAULT_TTL_HOURS = 24


def _alerta_producto_data_for_mensaje(alerta: AlertaProductoUrgente) -> dict:
    return {
        'id': alerta.id,
        'producto': alerta.producto,
        'cantidad': alerta.cantidad,
        'marca_modelo': alerta.marca_modelo or '',
        'status': alerta.status,
        'detalles': (alerta.detalles or '')[:160],
    }


def _mensaje_resolucion_alerta(alerta: AlertaProductoUrgente) -> str:
    """Texto corto; el detalle va en la card del chat (como trabajos/órdenes)."""
    return (
        f'Hola! Resolví mi pedido urgente de «{alerta.producto}» con ustedes. '
        '¿Coordinamos entrega o retiro?'
    )


def _abrir_chat_resolucion_alerta(usuario, alerta: AlertaProductoUrgente, respuesta: RespuestaAlertaProducto):
    """Crea o reusa el chat con el comercio y deja un mensaje con link a la alerta."""
    from django.db.models import Q
    from mensajeria.models import Chat, Mensajes
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    profesional = respuesta.profesional
    if profesional.id == usuario.id:
        return None

    chat = Chat.objects.filter(
        Q(sender=usuario, receiver=profesional) | Q(sender=profesional, receiver=usuario)
    ).first()
    if not chat:
        chat = Chat.objects.create(sender=usuario, receiver=profesional)

    alerta_data = _alerta_producto_data_for_mensaje(alerta)
    texto = _mensaje_resolucion_alerta(alerta)
    mensaje = Mensajes.objects.create(
        texto=texto,
        sender=usuario,
        chat=chat,
        tipo=Mensajes.TipoMensaje.TEXTO,
        metadata={
            'tipo': 'alerta_producto_urgente',
            'alerta_producto_id': alerta.id,
            'producto': alerta.producto,
            'cantidad': alerta.cantidad,
            'marca_modelo': alerta.marca_modelo or '',
            'status': alerta.status,
            'respuesta_id': respuesta.id,
        },
    )
    chat.ultimo_mensaje_at = mensaje.created_at
    chat.save(update_fields=['ultimo_mensaje_at'])

    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f'user_{profesional.id}',
                {
                    'type': 'chat_message',
                    'message': texto,
                    'mensaje_id': mensaje.mensaje_id,
                    'user_id': usuario.id,
                    'leido': False,
                    'chat_id': chat.id,
                    'alerta_producto': alerta_data,
                    'metadata': mensaje.metadata,
                    'chat': {
                        'id': chat.id,
                        'sender_id': chat.sender_id,
                        'receiver_id': chat.receiver_id,
                        'trabajo_id': None,
                        'ultimo_mensaje_at': chat.ultimo_mensaje_at.isoformat(),
                    },
                },
            )
    except Exception:
        pass

    try:
        from mensajeria.views import _notificar_mensaje_chat
        _notificar_mensaje_chat(chat, mensaje, usuario)
    except Exception:
        try:
            notificar_usuario.delay(
                profesional.id,
                'Pedido urgente resuelto con vos',
                (
                    f'{usuario.nombre or "Un cliente"} resolvió su alerta de '
                    f'«{alerta.producto}» y te escribió por chat.'
                ),
                {
                    'tipo': 'alerta_producto_resuelta',
                    'alerta_id': alerta.id,
                    'chat_id': chat.id,
                    'deep_link': f'/alertas?alertaProductoId={alerta.id}',
                },
            )
        except Exception:
            pass

    return chat.id


def _buscar_comercios_productos_cercanos(latitud, longitud, excluir_usuario_id=None):
    """Comercios con vende_productos cuyo admin cubre el punto con rango_mapa_km."""
    lat = float(latitud)
    lng = float(longitud)

    query = """
    WITH comercios AS (
        SELECT DISTINCT ON (e.admin_id_id)
            e.admin_id_id AS usuario_id,
            u.rango_mapa_km,
            l.latitud,
            l.longitud,
            ul.es_principal
        FROM empresa e
        INNER JOIN usuario u ON u.id = e.admin_id_id
        INNER JOIN usuario_localizacion ul ON ul.usuario_id = e.admin_id_id
        INNER JOIN localizacion l ON l.id = ul.localizacion_id
        WHERE e.vende_productos = TRUE
            AND e.is_deleted = FALSE
            AND e.deleted_at IS NULL
            AND ul.deleted_at IS NULL
            AND l.deleted_at IS NULL
            {excluir_clause}
        ORDER BY e.admin_id_id, ul.es_principal DESC NULLS LAST
    ),
    con_distancia AS (
        SELECT
            usuario_id,
            rango_mapa_km,
            (
                6371 * acos(
                    cos(radians(%s)) *
                    cos(radians(latitud)) *
                    cos(radians(longitud) - radians(%s)) +
                    sin(radians(%s)) *
                    sin(radians(latitud))
                )
            ) AS distancia_km
        FROM comercios
    )
    SELECT usuario_id
    FROM con_distancia
    WHERE distancia_km <= COALESCE(rango_mapa_km, 10.0)
    ORDER BY distancia_km ASC;
    """

    excluir_clause = ""
    if excluir_usuario_id:
        excluir_clause = "AND e.admin_id_id != %s"
        params = [excluir_usuario_id, lat, lng, lat]
    else:
        params = [lat, lng, lat]

    query = query.format(excluir_clause=excluir_clause)

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        ids = [row[0] for row in cursor.fetchall()]

    return filtrar_profesionales_fuera_zonas_exclusion(ids, lat, lng)


def _get_localizacion_usuario(usuario):
    loc = (
        UsuarioLocalizacion.objects.filter(usuario=usuario, localizacion__isPrimary=True)
        .select_related('localizacion')
        .first()
    )
    if not loc:
        loc = (
            UsuarioLocalizacion.objects.filter(usuario=usuario)
            .select_related('localizacion')
            .first()
        )
    return loc


def _expire_if_needed(alerta: AlertaProductoUrgente) -> AlertaProductoUrgente:
    if alerta.status in ('abierta', 'en_respuesta') and alerta.expires_at <= timezone.now():
        alerta.status = 'expirada'
        alerta.save(update_fields=['status', 'updated_at'])
    return alerta


class AlertaProductoUrgenteViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def create(self, request):
        serializer = AlertaProductoUrgenteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        usuario = request.user

        latitud = data['latitud']
        longitud = data['longitud']
        direccion = data.get('direccion') or ''

        localizacion = Localizacion.objects.filter(latitud=latitud, longitud=longitud).first()
        if not localizacion:
            localizacion = Localizacion.objects.create(
                ubicacion=direccion,
                latitud=latitud,
                longitud=longitud,
                address=direccion,
                isPrimary=False,
            )
            UsuarioLocalizacion.objects.create(
                usuario=usuario,
                localizacion=localizacion,
                es_principal=False,
            )

        comercios = _buscar_comercios_productos_cercanos(
            latitud, longitud, excluir_usuario_id=usuario.id
        )

        alerta = AlertaProductoUrgente.objects.create(
            usuario=usuario,
            producto=data['producto'],
            cantidad=data.get('cantidad') or 1,
            marca_modelo=(data.get('marca_modelo') or '').strip(),
            detalles=(data.get('detalles') or '').strip(),
            localizacion=localizacion,
            status='sin_entrega' if not comercios else 'abierta',
            expires_at=timezone.now() + timedelta(hours=DEFAULT_TTL_HOURS),
            comercios_notificados=len(comercios),
            created_by=usuario,
        )

        fotos = data.get('fotos') or []
        if fotos:
            AlertaProductoFoto.objects.bulk_create(
                [
                    AlertaProductoFoto(alerta=alerta, url=url, orden=i, created_by=usuario)
                    for i, url in enumerate(fotos[:3])
                ]
            )

        if comercios:
            notificar_usuarios_multiple.delay(
                usuarios_ids=comercios,
                titulo='Nueva alerta urgente de producto',
                mensaje=f'{data["producto"][:80]} · cantidad {data.get("cantidad") or 1}',
                data={
                    'deep_link': f'/alertas/productos/{alerta.id}',
                    'entity_id': alerta.id,
                    'tipo': 'nueva_alerta_producto_urgente',
                },
            )

        return Response(
            AlertaProductoUrgenteDetailSerializer(alerta, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    def list(self, request):
        """Listado para comercios con vende_productos (alertas en su cobertura)."""
        usuario = request.user
        empresa = Empresa.objects.filter(admin_id=usuario, vende_productos=True).first()
        if not empresa:
            return Response({
                'count': 0,
                'alertas': [],
                'message': 'Tu negocio no vende productos',
            })

        loc_user = _get_localizacion_usuario(usuario)
        if not loc_user:
            return Response({
                'count': 0,
                'alertas': [],
                'message': 'No tienes localización configurada',
            })

        status_filter = request.query_params.get('status')  # abierta|en_respuesta|all_active
        filter_param = request.query_params.get('filter', 'all')  # all|no_response|responded|disponible|no_disponible
        sort_param = request.query_params.get('sort', 'recent')

        now = timezone.now()
        qs = (
            AlertaProductoUrgente.objects.filter(
                is_deleted=False,
                expires_at__gte=now,
            )
            .exclude(usuario=usuario)
            .exclude(status__in=['cancelada', 'expirada', 'resuelta', 'sin_entrega'])
            .select_related('usuario', 'localizacion')
            .prefetch_related('fotos', 'respuestas')
        )

        if status_filter in ('abierta', 'en_respuesta'):
            qs = qs.filter(status=status_filter)
        else:
            qs = qs.filter(status__in=['abierta', 'en_respuesta'])

        if filter_param == 'no_response':
            qs = qs.exclude(respuestas__profesional=usuario)
        elif filter_param == 'responded':
            qs = qs.filter(respuestas__profesional=usuario)
        elif filter_param == 'disponible':
            qs = qs.filter(
                respuestas__profesional=usuario,
                respuestas__disponibilidad='disponible',
            )
        elif filter_param == 'no_disponible':
            qs = qs.filter(
                respuestas__profesional=usuario,
                respuestas__disponibilidad='no_disponible',
            )

        qs = qs.distinct()

        # Cobertura por rango del comercio
        rango = float(getattr(usuario, 'rango_mapa_km', None) or 10)
        lat_u = float(loc_user.localizacion.latitud)
        lng_u = float(loc_user.localizacion.longitud)

        alertas_cercanas = []
        for alerta in qs:
            if not alerta.localizacion_id:
                continue
            dist = calcular_distancia_km(
                lat_u,
                lng_u,
                float(alerta.localizacion.latitud),
                float(alerta.localizacion.longitud),
            )
            if dist <= rango:
                alertas_cercanas.append((alerta, dist))

        if sort_param == 'fewest_responses':
            alertas_cercanas.sort(
                key=lambda item: (
                    item[0].respuestas.filter(is_deleted=False).count(),
                    -item[0].created_at.timestamp(),
                )
            )
        elif sort_param == 'soonest':
            alertas_cercanas.sort(key=lambda item: item[0].expires_at)
        else:
            alertas_cercanas.sort(key=lambda item: item[0].created_at, reverse=True)

        resultado = []
        for alerta, dist in alertas_cercanas:
            payload = AlertaProductoUrgenteDetailSerializer(
                alerta, context={'request': request}
            ).data
            payload['distancia_km'] = round(dist, 2)
            resultado.append(payload)

        return Response({'count': len(resultado), 'alertas': resultado})

    def retrieve(self, request, pk=None):
        try:
            alerta = (
                AlertaProductoUrgente.objects.select_related('usuario', 'localizacion')
                .prefetch_related('fotos', 'respuestas__profesional', 'respuestas__empresa')
                .get(id=pk, is_deleted=False)
            )
        except AlertaProductoUrgente.DoesNotExist:
            return Response({'error': 'Alerta no encontrada'}, status=status.HTTP_404_NOT_FOUND)

        _expire_if_needed(alerta)
        return Response(
            AlertaProductoUrgenteDetailSerializer(alerta, context={'request': request}).data
        )

    @action(detail=False, methods=['get'], url_path='mis-solicitudes')
    def mis_solicitudes(self, request):
        status_filter = request.query_params.get('status')
        qs = (
            AlertaProductoUrgente.objects.filter(usuario=request.user, is_deleted=False)
            .select_related('localizacion', 'usuario')
            .prefetch_related('fotos', 'respuestas__profesional', 'respuestas__empresa')
            .order_by('-created_at')
        )
        for alerta in qs:
            _expire_if_needed(alerta)

        if status_filter:
            if status_filter == 'activas':
                qs = qs.filter(status__in=['abierta', 'en_respuesta'])
            else:
                qs = qs.filter(status=status_filter)

        data = AlertaProductoUrgenteDetailSerializer(
            qs, many=True, context={'request': request}
        ).data
        return Response({'count': len(data), 'alertas': data})

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def responder(self, request, pk=None):
        try:
            alerta = AlertaProductoUrgente.objects.select_for_update().get(
                id=pk, is_deleted=False
            )
        except AlertaProductoUrgente.DoesNotExist:
            return Response({'error': 'Alerta no encontrada'}, status=status.HTTP_404_NOT_FOUND)

        _expire_if_needed(alerta)

        if alerta.usuario_id == request.user.id:
            return Response(
                {'error': 'No podés responder tu propia alerta'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if alerta.status in ('cancelada', 'expirada', 'resuelta', 'sin_entrega'):
            return Response(
                {'error': 'Esta alerta ya no acepta respuestas'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if alerta.expires_at <= timezone.now():
            alerta.status = 'expirada'
            alerta.save(update_fields=['status', 'updated_at'])
            return Response(
                {'error': 'Esta alerta expiró'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        empresa = Empresa.objects.filter(admin_id=request.user, vende_productos=True).first()
        if not empresa:
            return Response(
                {'error': 'Solo comercios con venta de productos pueden responder'},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = RespuestaAlertaProductoCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        existing = RespuestaAlertaProducto.objects.filter(
            alerta=alerta, profesional=request.user
        ).first()
        if existing and not existing.is_deleted:
            return Response(
                {'error': 'Ya respondiste esta alerta'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if existing and existing.is_deleted:
            existing.is_deleted = False
            existing.deleted_at = None
            existing.disponibilidad = serializer.validated_data['disponibilidad']
            existing.mensaje = serializer.validated_data.get('mensaje') or ''
            existing.empresa = empresa
            existing.save()
            respuesta = existing
        else:
            respuesta = RespuestaAlertaProducto.objects.create(
                alerta=alerta,
                profesional=request.user,
                empresa=empresa,
                disponibilidad=serializer.validated_data['disponibilidad'],
                mensaje=serializer.validated_data.get('mensaje') or '',
                created_by=request.user,
            )

        if alerta.status == 'abierta':
            alerta.status = 'en_respuesta'
            alerta.save(update_fields=['status', 'updated_at'])

        disp_label = (
            'tiene el producto'
            if respuesta.disponibilidad == 'disponible'
            else 'no tiene el producto'
        )
        notificar_usuario.delay(
            usuario_id=alerta.usuario_id,
            titulo='Nueva respuesta a tu alerta de producto',
            mensaje=f'{empresa.nombre} {disp_label}',
            data={
                'deep_link': f'/alertas/productos/{alerta.id}',
                'entity_id': respuesta.id,
                'tipo': 'respuesta_alerta_producto',
            },
        )

        return Response(
            RespuestaAlertaProductoSerializer(respuesta, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['get'])
    def respuestas(self, request, pk=None):
        try:
            alerta = AlertaProductoUrgente.objects.get(id=pk, is_deleted=False)
        except AlertaProductoUrgente.DoesNotExist:
            return Response({'error': 'Alerta no encontrada'}, status=status.HTTP_404_NOT_FOUND)

        if alerta.usuario_id == request.user.id:
            qs = (
                alerta.respuestas.filter(is_deleted=False)
                .select_related('profesional', 'empresa')
                .order_by('-created_at')
            )
            data = RespuestaAlertaProductoSerializer(qs, many=True, context={'request': request}).data
            return Response({'count': len(data), 'respuestas': data})

        mine = (
            alerta.respuestas.filter(profesional=request.user, is_deleted=False)
            .select_related('profesional', 'empresa')
            .first()
        )
        data = (
            [RespuestaAlertaProductoSerializer(mine, context={'request': request}).data]
            if mine
            else []
        )
        return Response({
            'count': data and 1 or 0,
            'respuestas': data,
            'cantidad_respuestas': alerta.respuestas.filter(is_deleted=False).count(),
        })

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def cancelar(self, request, pk=None):
        try:
            alerta = AlertaProductoUrgente.objects.select_for_update().get(
                id=pk, is_deleted=False, usuario=request.user
            )
        except AlertaProductoUrgente.DoesNotExist:
            return Response({'error': 'Alerta no encontrada'}, status=status.HTTP_404_NOT_FOUND)

        if alerta.status in ('cancelada', 'expirada', 'resuelta'):
            return Response(
                {'error': 'La alerta ya está cerrada'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        alerta.status = 'cancelada'
        alerta.save(update_fields=['status', 'updated_at'])
        return Response(
            AlertaProductoUrgenteDetailSerializer(alerta, context={'request': request}).data
        )

    @action(detail=True, methods=['post'])
    @transaction.atomic
    def resolver(self, request, pk=None):
        try:
            alerta = AlertaProductoUrgente.objects.select_for_update().get(
                id=pk, is_deleted=False, usuario=request.user
            )
        except AlertaProductoUrgente.DoesNotExist:
            return Response({'error': 'Alerta no encontrada'}, status=status.HTTP_404_NOT_FOUND)

        if alerta.status in ('cancelada', 'expirada', 'resuelta'):
            return Response(
                {'error': 'La alerta ya está cerrada'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        respuestas_qs = alerta.respuestas.filter(is_deleted=False).select_related(
            'profesional', 'empresa'
        )
        respuesta_id = request.data.get('respuesta_id')
        respuesta = None
        if respuestas_qs.exists():
            if not respuesta_id:
                return Response(
                    {'error': 'Seleccioná con qué comercio resolviste la alerta'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                respuesta = respuestas_qs.get(id=int(respuesta_id))
            except (RespuestaAlertaProducto.DoesNotExist, TypeError, ValueError):
                return Response(
                    {'error': 'La propuesta elegida no pertenece a esta alerta'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        alerta.status = 'resuelta'
        alerta.respuesta_aceptada = respuesta
        alerta.save(update_fields=['status', 'respuesta_aceptada', 'updated_at'])

        chat_id = None
        if respuesta is not None:
            chat_id = _abrir_chat_resolucion_alerta(request.user, alerta, respuesta)

        data = AlertaProductoUrgenteDetailSerializer(alerta, context={'request': request}).data
        data['chat_id'] = chat_id
        return Response(data)

    @action(detail=False, methods=['get'], url_path='mis-respuestas')
    def mis_respuestas(self, request):
        status_filter = request.query_params.get('status')
        qs = (
            RespuestaAlertaProducto.objects.filter(
                profesional=request.user, is_deleted=False
            )
            .select_related('alerta', 'alerta__localizacion', 'alerta__usuario', 'empresa')
            .prefetch_related('alerta__fotos')
            .order_by('-created_at')
        )
        if status_filter in ('disponible', 'no_disponible'):
            qs = qs.filter(disponibilidad=status_filter)

        alertas = []
        for respuesta in qs:
            alerta = respuesta.alerta
            payload = AlertaProductoUrgenteDetailSerializer(
                alerta, context={'request': request}
            ).data
            payload['mi_respuesta'] = RespuestaAlertaProductoSerializer(
                respuesta, context={'request': request}
            ).data
            alertas.append(payload)

        return Response({'count': len(alertas), 'alertas': alertas})
