from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Chat, Mensajes, Recurso
from .serializers import ChatSerializer, MensajesSerializer, RecursoSerializer


class ChatViewSet(viewsets.ModelViewSet):
    queryset = Chat.objects.all()
    serializer_class = ChatSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        user_id = self.request.query_params.get('user_id', None)
        if user_id:
            queryset = queryset.filter(sender_id=user_id) | queryset.filter(received_id=user_id)
        return queryset


class MensajesViewSet(viewsets.ModelViewSet):
    queryset = Mensajes.objects.all()
    serializer_class = MensajesSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        chat_id = self.request.query_params.get('chat_id', None)
        if chat_id:
            queryset = queryset.filter(chat_id=chat_id)
        return queryset


class RecursoViewSet(viewsets.ModelViewSet):
    queryset = Recurso.objects.all()
    serializer_class = RecursoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        mensaje_id = self.request.query_params.get('mensaje_id', None)
        if mensaje_id:
            queryset = queryset.filter(mensaje_id=mensaje_id)
        return queryset

