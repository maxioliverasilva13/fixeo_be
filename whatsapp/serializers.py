from rest_framework import serializers

from .models import WhatsAppMessage


class WhatsAppMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhatsAppMessage
        fields = [
            'id', 'wa_id', 'usuario', 'direccion', 'tipo',
            'wa_message_id', 'estado', 'texto', 'payload',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields


class EnviarMensajeSerializer(serializers.Serializer):
    to = serializers.CharField(max_length=32)
    body = serializers.CharField()
