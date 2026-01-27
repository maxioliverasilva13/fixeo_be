from rest_framework import serializers
from .models import Chat, Mensajes, Recurso


class RecursoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recurso
        fields = '__all__'


class MensajesSerializer(serializers.ModelSerializer):
    recursos = RecursoSerializer(many=True, read_only=True)
    
    class Meta:
        model = Mensajes
        fields = '__all__'


class ChatSerializer(serializers.ModelSerializer):
    mensajes = MensajesSerializer(many=True, read_only=True)
    
    class Meta:
        model = Chat
        fields = '__all__'

