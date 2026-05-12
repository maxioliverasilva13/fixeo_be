from notificaciones.tasks import notificar_usuario
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q, Max
from django.shortcuts import get_object_or_404
from usuario.models import Usuario
from trabajos.models import Trabajo
from .models import Chat, Mensajes, Recurso
from .serializers import (
    ChatSerializer, ChatCreateSerializer,
    MensajesSerializer, MensajeCreateSerializer,
    RecursoSerializer, RecursoCreateSerializer
)
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.db.models import OuterRef, Subquery

class ChatPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class MensajePagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class ChatViewSet(viewsets.ModelViewSet):
    serializer_class = ChatSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ChatPagination

    @staticmethod
    def _crear_mensaje_calificacion(chat, sender, puntaje, comentario=''):
        mensaje = Mensajes.objects.create(
            texto='',
            sender=sender,
            chat=chat,
            tipo=Mensajes.TipoMensaje.CALIFICACION,
            metadata={
                'puntaje': puntaje,
                'comentario': comentario,
            }
        )
        chat.ultimo_mensaje_at = mensaje.created_at
        chat.save()

        received_user = chat.receiver if sender.id == chat.sender_id else chat.sender
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(f'user_{received_user.id}', {
            'type': 'chat_message',
            'mensaje_id': mensaje.mensaje_id,
            'user_id': sender.id,
            'created_at': mensaje.created_at.isoformat(),
            'chat_id': chat.id,
            'leido': False,
            'tipo': Mensajes.TipoMensaje.CALIFICACION,
            'metadata': mensaje.metadata,
            'recurso': None,
        })
        return mensaje
        
    def get_queryset(self):
        user = self.request.user
        return Chat.objects.filter(
            Q(sender=user) | Q(receiver=user)
        ).select_related('sender', 'receiver', 'trabajo').prefetch_related('mensajes').order_by('-ultimo_mensaje_at')
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def create(self, request, *args, **kwargs):
        serializer = ChatCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        receiver_id = serializer.validated_data['receiver_id']
        trabajo_id = serializer.validated_data.get('trabajo_id')
        mensaje_inicial = serializer.validated_data.get('mensaje_inicial')

        if receiver_id == request.user.id:
            return Response(
                {'error': 'No puedes crear un chat contigo mismo'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            receiver = Usuario.objects.get(id=receiver_id)
        except Usuario.DoesNotExist:
            return Response(
                {'error': 'El usuario receptor no existe'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        trabajo = None
        if trabajo_id:
            try:
                trabajo = Trabajo.objects.get(id=trabajo_id)
            except Trabajo.DoesNotExist:
                return Response(
                    {'error': 'El trabajo no existe'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        chat = Chat.objects.filter(
            Q(sender=request.user, receiver=receiver) |
            Q(sender=receiver, receiver=request.user)
        ).first()
        
        if chat:
            return Response(
                ChatSerializer(chat, context={'request': request}).data,
                status=status.HTTP_200_OK
            )
        
        chat = Chat.objects.create(
            sender=request.user,
            receiver=receiver,
            trabajo=trabajo
        )
        
        if mensaje_inicial:
            Mensajes.objects.create(
                texto=mensaje_inicial,
                sender=request.user,
                chat=chat,
                tipo=Mensajes.TipoMensaje.TEXTO, 

            )
            chat.ultimo_mensaje_at = chat.created_at
            chat.save()

        room_name = f"usuario_channel_{chat.receiver.id}"

        print(f"[CHAT CREATED] chat_id={chat.id} room_name={room_name} sender_id={request.user.id} receiver_id={receiver.id}")

        channel_layer = get_channel_layer()

        payload = {
            'type': 'chat_message',
            'message': mensaje_inicial if mensaje_inicial else '',
            'user_id': request.user.id,
            'leido': False,
            'chat_id': chat.id,
            'chat': {
                'id': chat.id,
                'sender_id': chat.sender.id,
                'sender_nombre': f"{chat.sender.nombre} {chat.sender.apellido}",
                'receiver_id': chat.receiver.id,
                'receiver_nombre': f"{chat.receiver.nombre} {chat.receiver.apellido}",
                'trabajo_id': chat.trabajo.id if chat.trabajo else None,
                'ultimo_mensaje_at': chat.ultimo_mensaje_at.isoformat(),
            }
        }

        async_to_sync(channel_layer.group_send)(f'user_{chat.receiver.id}', payload)
        
        print('10')
        return Response(
            ChatSerializer(chat, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['get'])
    def mensajes(self, request, pk=None):
        chat = self.get_object()
        
        if chat.sender != request.user and chat.receiver != request.user:
            return Response(
                {'error': 'No tienes permiso para ver estos mensajes'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        mensajes = chat.mensajes.select_related('sender', 'trabajo').prefetch_related('recursos').order_by('-created_at')
        
        paginator = MensajePagination()
        page = paginator.paginate_queryset(mensajes, request)
        
        if page is not None:
            serializer = MensajesSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
        serializer = MensajesSerializer(mensajes, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def enviar_mensaje(self, request, pk=None):
        chat = self.get_object()
        
        if chat.sender != request.user and chat.receiver != request.user:
            return Response(
                {'error': 'No tienes permiso para enviar mensajes en este chat'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = MensajeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        recurso = None
        if serializer.validated_data.get('recurso_id'):
            try:
                recurso = Recurso.objects.get(
                    id=serializer.validated_data['recurso_id'],
                    chat=chat,
                    mensaje__isnull=True
                )
            except Recurso.DoesNotExist:
                return Response(
                    {'error': 'El recurso no existe o ya está asociado a otro mensaje'},
                    status=status.HTTP_404_NOT_FOUND
                )

        mensaje = Mensajes.objects.create(
            texto=serializer.validated_data['texto'],
            sender=request.user,
            chat=chat,
            tipo=Mensajes.TipoMensaje.TEXTO,  
        )

        received_user = chat.receiver if request.user.id == chat.sender_id else chat.sender

        room_name = f"usuario_channel_{received_user.id}"

        channel_layer = get_channel_layer()

        payload = {
            'type': 'chat_message',
            'message': mensaje.texto,
            'mensaje_id': mensaje.mensaje_id,
            'user_id': request.user.id,
            'created_at': mensaje.created_at.isoformat(),
            'chat_id': chat.id,
            'leido': mensaje.leido,
            'tipo': mensaje.tipo,        # ← agregar
            'metadata': mensaje.metadata, # ← agregar
            'recurso': {
                'id': recurso.id,
                'url': recurso.url,
                'tipo': recurso.tipo,
                'nombre': recurso.nombre,
            } if recurso else None,
        }

        async_to_sync(channel_layer.group_send)(f'user_{received_user.id}', payload)

        userNameToReceive = None
        userIdToReceive = None
        if (request.user.id == chat.sender.id):
            userIdToReceive = chat.receiver.id
            userNameToReceive = chat.receiver.nombre
        else:
            userIdToReceive = chat.sender.id
            userNameToReceive = chat.sender.nombre

        notificar_usuario.delay(
            usuario_id=userIdToReceive,
            titulo=f"Nuevo mensaje de {userNameToReceive}",
            mensaje=mensaje.texto,
            data={
                'deep_link': f'/chats/{chat.id}',
                'entity_id': chat.id
            }
        )
        
        if recurso:
            recurso.mensaje = mensaje
            recurso.save()
        
        chat.ultimo_mensaje_at = mensaje.created_at
        chat.save()
        
        return Response(
            MensajesSerializer(mensaje).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['post'])
    def subir_recurso(self, request, pk=None):
        chat = self.get_object()
        
        if chat.sender != request.user and chat.receiver != request.user:
            return Response(
                {'error': 'No tienes permiso para subir recursos en este chat'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = RecursoCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        recurso = Recurso.objects.create(
            url=serializer.validated_data['url'],
            tipo=serializer.validated_data.get('tipo', ''),
            nombre=serializer.validated_data.get('nombre', ''),
            chat=chat
        )
        
        return Response(
            RecursoSerializer(recurso).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['get'])
    def recursos(self, request, pk=None):
        chat = self.get_object()
        
        if chat.sender != request.user and chat.receiver != request.user:
            return Response(
                {'error': 'No tienes permiso para ver los recursos de este chat'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        recursos = chat.recursos.all().order_by('-created_at')
        serializer = RecursoSerializer(recursos, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def marcar_leido(self, request, pk=None):
        chat = self.get_object()
        
        if chat.sender != request.user and chat.receiver != request.user:
            return Response(
                {'error': 'No tienes permiso para marcar mensajes en este chat'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        mensajes_actualizados = chat.mensajes.filter(
            leido=False
        ).exclude(sender=request.user).update(leido=True)

        mensajes_no_leidos = chat.mensajes.filter(
            leido=False
        ).exclude(sender=request.user)

        mensaje_ids = list(mensajes_no_leidos.values_list('mensaje_id', flat=True))

        mensajes_actualizados = mensajes_no_leidos.update(leido=True)

        received_user = chat.receiver if request.user.id == chat.sender_id else chat.sender
        room_name = f"usuario_channel_{received_user.id}"

        payload = {
            'type': 'chat_read', 
            'chat_id': chat.id,
            'reader_id': request.user.id,
            'mensaje_ids': mensaje_ids,
        }

        channel_layer = get_channel_layer()

        async_to_sync(channel_layer.group_send)(f'user_{received_user.id}', payload)

        return Response({
            'message': f'{mensajes_actualizados} mensajes marcados como leídos'
        })
    
    @action(detail=False, methods=['get'], url_path='no-leidos')
    def mensajes_no_leidos(self, request):
        count = Mensajes.objects.filter(
            chat__in=Chat.objects.filter(
                Q(sender=request.user) | Q(receiver=request.user)
            ),
            leido=False,
        ).exclude(
            sender=request.user
        ).count()

        return Response({'no_leidos': count})

    @action(detail=True, methods=['delete'], url_path='mensajes/(?P<mensaje_id>[^/.]+)')
    def eliminar_mensaje(self, request, pk=None, mensaje_id=None):
        """
        Elimina un mensaje del chat.
        Solo el sender del mensaje puede eliminarlo.
        """
        chat = self.get_object()
        
        if chat.sender != request.user and chat.receiver != request.user:
            return Response(
                {'error': 'No tienes permiso para eliminar mensajes en este chat'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            mensaje = Mensajes.objects.get(mensaje_id=mensaje_id, chat=chat)
        except Mensajes.DoesNotExist:
            return Response(
                {'error': 'El mensaje no existe'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if mensaje.sender != request.user:
            return Response(
                {'error': 'Solo puedes eliminar tus propios mensajes'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        other_user = chat.receiver if request.user.id == chat.sender_id else chat.sender
        
        deleted_mensaje_id = mensaje.mensaje_id
        
        mensaje.delete()
        
        channel_layer = get_channel_layer()
        payload = {
            'type': 'mensaje_eliminado',
            'chat_id': chat.id,
            'mensaje_id': deleted_mensaje_id,
            'deleted_by': request.user.id,
        }
        
        async_to_sync(channel_layer.group_send)(f'user_{chat.sender.id}', payload)
        async_to_sync(channel_layer.group_send)(f'user_{chat.receiver.id}', payload)
        
        return Response(
            {'message': 'Mensaje eliminado correctamente', 'mensaje_id': deleted_mensaje_id},
            status=status.HTTP_200_OK
        )
