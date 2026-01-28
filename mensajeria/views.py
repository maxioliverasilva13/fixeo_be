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
                chat=chat
            )
            chat.ultimo_mensaje_at = chat.created_at
            chat.save()
        
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
        
        mensajes = chat.mensajes.select_related('sender').prefetch_related('recursos').order_by('-created_at')
        
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
            chat=chat
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
        
        return Response({
            'message': f'{mensajes_actualizados} mensajes marcados como leídos'
        })
