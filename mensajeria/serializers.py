from rest_framework import serializers
from usuario.utils import foto_usuario_api
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
    trabajo = serializers.SerializerMethodField()
    orden = serializers.SerializerMethodField()

    class Meta:
        model = Mensajes
        fields = [
            'mensaje_id', 'texto', 'tipo', 'metadata',
            'sender', 'sender_nombre', 'chat', 'leido',
            'recursos', 'created_at', 'updated_at', 'trabajo', 'orden', 'calificado'
        ]
        read_only_fields = ['mensaje_id', 'sender', 'created_at', 'updated_at']

    def get_sender_nombre(self, obj):
        return f"{obj.sender.nombre} {obj.sender.apellido}"

    def get_trabajo(self, obj):
        if not obj.trabajo_id:
            return None
        from trabajos.serializers import TrabajoMensajeResumenSerializer
        return TrabajoMensajeResumenSerializer(obj.trabajo).data

    def get_orden(self, obj):
        metadata = obj.metadata or {}
        orden_id = metadata.get('orden_id')
        if not orden_id:
            return None
        from carritos.models import Orden
        from carritos.chat_helpers import _orden_data_for_mensaje
        try:
            orden = Orden.objects.select_related('empresa').get(pk=orden_id)
        except Orden.DoesNotExist:
            return None
        return _orden_data_for_mensaje(orden, metadata)

class MensajeCreateSerializer(serializers.Serializer):
    texto      = serializers.CharField(required=False, allow_blank=True, default='')
    recurso_id = serializers.IntegerField(required=False)

    def validate(self, data):
        if not data.get('texto', '').strip() and not data.get('recurso_id'):
            raise serializers.ValidationError('Debes enviar texto o un recurso.')
        return data

class ChatSerializer(serializers.ModelSerializer):
    sender_nombre = serializers.SerializerMethodField()
    sender_photo_rounded = serializers.SerializerMethodField()
    receiver_nombre = serializers.SerializerMethodField()
    receiver_photo_rounded = serializers.SerializerMethodField()
    trabajo_info = serializers.SerializerMethodField()
    ultimo_mensaje = serializers.SerializerMethodField()
    mensajes_no_leidos = serializers.SerializerMethodField()
    
    class Meta:
        model = Chat
        fields = ['id', 'sender', 'sender_nombre', 'sender_photo_rounded', 'receiver', 
                  'receiver_nombre', 'receiver_photo_rounded', 'trabajo', 'trabajo_info', 
                  'ultimo_mensaje_at', 'ultimo_mensaje', 'mensajes_no_leidos', 'created_at', 
                  'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_sender_nombre(self, obj):
        return f"{obj.sender.nombre} {obj.sender.apellido}"
    
    def get_sender_photo_rounded(self, obj):
        u = obj.sender
        return foto_usuario_api(u.rounded_foto_url or u.foto_url)

    def get_receiver_nombre(self, obj):
        return f"{obj.receiver.nombre} {obj.receiver.apellido}"

    def get_receiver_photo_rounded(self, obj):
        u = obj.receiver
        return foto_usuario_api(u.rounded_foto_url or u.foto_url)
    
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
        if not ultimo:
            return None
        
        texto = ultimo.texto
        if ultimo.tipo == 'imagen':
            recurso = ultimo.recursos.first()
            texto = recurso.url if recurso else ''
        elif ultimo.tipo == 'archivo':
            recurso = ultimo.recursos.first()
            texto = recurso.nombre or recurso.url if recurso else ''

        return {
            'texto': texto,
            'sender': ultimo.sender.id,
            'created_at': ultimo.created_at,
            'leido': ultimo.leido,
            'tipo': ultimo.tipo,
            'metadata': ultimo.metadata,
        }
        
    def get_mensajes_no_leidos(self, obj):
        request = self.context.get('request')
        if request and request.user:
            return obj.mensajes.filter(leido=False).exclude(sender=request.user).count()
        return 0


class ChatCreateSerializer(serializers.Serializer):
    receiver_id = serializers.IntegerField(required=True)
    trabajo_id = serializers.IntegerField(required=False, allow_null=True)
    mensaje_inicial = serializers.CharField(required=False, allow_blank=True)

