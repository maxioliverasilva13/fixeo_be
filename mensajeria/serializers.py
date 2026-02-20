from rest_framework import serializers
from .models import Chat, Mensajes, Recurso


class RecursoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recurso
        fields = ['id', 'url', 'tipo', 'nombre', 'created_at']
        read_only_fields = ['id', 'created_at']


class RecursoCreateSerializer(serializers.Serializer):
    url = serializers.URLField(required=True)
    tipo = serializers.CharField(required=False, allow_blank=True, max_length=50)
    nombre = serializers.CharField(required=False, allow_blank=True, max_length=255)


class MensajesSerializer(serializers.ModelSerializer):
    recursos = RecursoSerializer(many=True, read_only=True)
    sender_nombre = serializers.SerializerMethodField()
    
    class Meta:
        model = Mensajes
        fields = ['mensaje_id', 'texto', 'sender', 'sender_nombre', 'chat', 'leido', 'recursos', 'created_at', 'updated_at']
        read_only_fields = ['mensaje_id', 'sender', 'created_at', 'updated_at']
    
    def get_sender_nombre(self, obj):
        return f"{obj.sender.nombre} {obj.sender.apellido}"


class MensajeCreateSerializer(serializers.Serializer):
    texto = serializers.CharField(required=True)
    recurso_id = serializers.IntegerField(required=False, allow_null=True)


class ChatSerializer(serializers.ModelSerializer):
    sender_nombre = serializers.SerializerMethodField()
    receiver_nombre = serializers.SerializerMethodField()
    trabajo_info = serializers.SerializerMethodField()
    ultimo_mensaje = serializers.SerializerMethodField()
    mensajes_no_leidos = serializers.SerializerMethodField()
    
    class Meta:
        model = Chat
        fields = ['id', 'sender', 'sender_nombre', 'receiver', 'receiver_nombre', 
                  'trabajo', 'trabajo_info', 'ultimo_mensaje_at', 'ultimo_mensaje', 
                  'mensajes_no_leidos', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_sender_nombre(self, obj):
        return f"{obj.sender.nombre} {obj.sender.apellido}"
    
    def get_receiver_nombre(self, obj):
        return f"{obj.receiver.nombre} {obj.receiver.apellido}"
    
    def get_trabajo_info(self, obj):
        if obj.trabajo:
            return {
                'id': obj.trabajo.id,
                'titulo': obj.trabajo.descripcion,
                'status': obj.trabajo.status,
                'precio_final': float(obj.trabajo.precio_final) if obj.trabajo.precio_final else None
            }
        return None
    
    def get_ultimo_mensaje(self, obj):
        ultimo = obj.mensajes.first()
        if ultimo:
            return {
                'texto': ultimo.texto,
                'sender': ultimo.sender.id,
                'created_at': ultimo.created_at
            }
        return None
    
    def get_mensajes_no_leidos(self, obj):
        request = self.context.get('request')
        if request and request.user:
            return obj.mensajes.filter(leido=False).exclude(sender=request.user).count()
        return 0


class ChatCreateSerializer(serializers.Serializer):
    receiver_id = serializers.IntegerField(required=True)
    trabajo_id = serializers.IntegerField(required=False, allow_null=True)
    mensaje_inicial = serializers.CharField(required=False, allow_blank=True)

