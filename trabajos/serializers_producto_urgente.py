from rest_framework import serializers
from .models import AlertaProductoUrgente, AlertaProductoFoto, RespuestaAlertaProducto


class AlertaProductoUrgenteCreateSerializer(serializers.Serializer):
    producto = serializers.CharField(max_length=200)
    cantidad = serializers.IntegerField(min_value=1, default=1)
    marca_modelo = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    detalles = serializers.CharField(required=False, allow_blank=True, default='')
    latitud = serializers.FloatField()
    longitud = serializers.FloatField()
    direccion = serializers.CharField(required=False, allow_blank=True, default='')
    fotos = serializers.ListField(
        child=serializers.URLField(max_length=500),
        required=False,
        allow_empty=True,
        max_length=3,
    )

    def validate_producto(self, value):
        cleaned = (value or '').strip()
        if not cleaned:
            raise serializers.ValidationError('El producto es obligatorio.')
        return cleaned


class RespuestaAlertaProductoCreateSerializer(serializers.Serializer):
    disponibilidad = serializers.ChoiceField(choices=['disponible', 'no_disponible'])
    mensaje = serializers.CharField(required=False, allow_blank=True, default='')


class AlertaProductoFotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertaProductoFoto
        fields = ['id', 'url', 'orden']


class RespuestaAlertaProductoSerializer(serializers.ModelSerializer):
    profesional = serializers.SerializerMethodField()
    empresa = serializers.SerializerMethodField()

    class Meta:
        model = RespuestaAlertaProducto
        fields = [
            'id',
            'disponibilidad',
            'mensaje',
            'profesional',
            'empresa',
            'created_at',
        ]

    def get_profesional(self, obj):
        from usuario.utils import foto_usuario_api

        u = obj.profesional
        return {
            'id': u.id,
            'nombre': u.nombre,
            'apellido': u.apellido,
            'foto_url': foto_usuario_api(getattr(u, 'foto_url', None)),
            'rounded_foto_url': foto_usuario_api(getattr(u, 'rounded_foto_url', None)),
            'rating': float(getattr(u, 'rating', 0) or 0),
            'cant_calif': int(getattr(u, 'cant_calif', 0) or 0),
        }

    def get_empresa(self, obj):
        e = obj.empresa
        if not e:
            return None
        return {
            'id': e.id,
            'nombre': e.nombre,
            'vende_productos': e.vende_productos,
        }


class AlertaProductoUrgenteDetailSerializer(serializers.ModelSerializer):
    fotos = AlertaProductoFotoSerializer(many=True, read_only=True)
    localizacion = serializers.SerializerMethodField()
    usuario = serializers.SerializerMethodField()
    cantidad_respuestas = serializers.SerializerMethodField()
    cantidad_disponibles = serializers.SerializerMethodField()
    mi_respuesta = serializers.SerializerMethodField()
    respuestas = serializers.SerializerMethodField()

    class Meta:
        model = AlertaProductoUrgente
        fields = [
            'id',
            'producto',
            'cantidad',
            'marca_modelo',
            'detalles',
            'status',
            'expires_at',
            'created_at',
            'comercios_notificados',
            'fotos',
            'localizacion',
            'usuario',
            'cantidad_respuestas',
            'cantidad_disponibles',
            'mi_respuesta',
            'respuestas',
        ]

    def get_localizacion(self, obj):
        loc = obj.localizacion
        if not loc:
            return None
        return {
            'latitud': float(loc.latitud) if loc.latitud is not None else None,
            'longitud': float(loc.longitud) if loc.longitud is not None else None,
            'ubicacion': loc.ubicacion or loc.address or '',
            'direccion': loc.ubicacion or loc.address or '',
        }

    def get_usuario(self, obj):
        u = obj.usuario
        return {
            'id': u.id,
            'nombre': u.nombre,
            'apellido': u.apellido,
            'foto_url': getattr(u, 'foto_url', None),
            'rounded_foto_url': getattr(u, 'rounded_foto_url', None),
        }

    def get_cantidad_respuestas(self, obj):
        prefetched = getattr(obj, '_prefetched_objects_cache', {}).get('respuestas')
        if prefetched is not None:
            return len(prefetched)
        return obj.respuestas.filter(is_deleted=False).count()

    def get_cantidad_disponibles(self, obj):
        prefetched = getattr(obj, '_prefetched_objects_cache', {}).get('respuestas')
        if prefetched is not None:
            return sum(1 for r in prefetched if r.disponibilidad == 'disponible')
        return obj.respuestas.filter(is_deleted=False, disponibilidad='disponible').count()

    def get_mi_respuesta(self, obj):
        request = self.context.get('request')
        if not request or not request.user or not request.user.is_authenticated:
            return None
        prefetched = getattr(obj, '_prefetched_objects_cache', {}).get('respuestas')
        if prefetched is not None:
            mine = next((r for r in prefetched if r.profesional_id == request.user.id), None)
        else:
            mine = obj.respuestas.filter(profesional=request.user, is_deleted=False).first()
        if not mine:
            return None
        return RespuestaAlertaProductoSerializer(mine, context=self.context).data

    def get_respuestas(self, obj):
        """
        Solo el creador ve todas las respuestas.
        Un comercio solo ve la suya (vía mi_respuesta); acá no se listan las ajenas.
        """
        request = self.context.get('request')
        if not request or not request.user or not request.user.is_authenticated:
            return []
        if obj.usuario_id != request.user.id:
            return []
        qs = obj.respuestas.filter(is_deleted=False).select_related('profesional', 'empresa')
        return RespuestaAlertaProductoSerializer(qs, many=True, context=self.context).data
