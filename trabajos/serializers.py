from rest_framework import serializers
from .models import Trabajo, Calificacion, TrabajoServicio, OfertaTrabajo
from usuario.serializers import UsuarioSerializer, UsuarioSortSerializer, UsuarioBasicInformationSerializer
from servicios.serializers import ServicioSerializer 
from profesion.serializers import ProfesionSerializer 
from localizacion.serializers import LocalizacionSerializer
from servicios.models import Servicio

class CalificacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Calificacion
        fields = '__all__'


class TrabajoSerializer(serializers.ModelSerializer):
    calificaciones = CalificacionSerializer(many=True, read_only=True)
    
    class Meta:
        model = Trabajo
        fields = '__all__'

class TrabajoUrgenteCreateSerializer(serializers.Serializer):
    descripcion = serializers.CharField(required=True)
    profesion_id = serializers.IntegerField(required=True)
    latitud = serializers.DecimalField(max_digits=10, decimal_places=7, required=True)
    longitud = serializers.DecimalField(max_digits=10, decimal_places=7, required=True)
    direccion = serializers.CharField(required=False, allow_blank=True)
    fecha = serializers.DateField(required=True)
    hora = serializers.TimeField(required=True)

    def validate_fecha(self, value):
        from datetime import date
        if value < date.today():
            raise serializers.ValidationError("La fecha no puede ser en el pasado.")
        return value
    
class TrabajoServicioDetailSerializer(serializers.ModelSerializer):
    servicio = ServicioSerializer(read_only=True)
    
    class Meta:
        model = TrabajoServicio
        fields = ['id', 'servicio', 'precio', 'created_at']

class CalificacionDetailSerializer(serializers.ModelSerializer):
    user_cal_sender_nombre = serializers.CharField(source='user_cal_sender.nombre', read_only=True)
    user_cal_sender_apellido = serializers.CharField(source='user_cal_sender.apellido', read_only=True)
    
    class Meta:
        model = Calificacion
        fields = ['id', 'rating', 'comentario', 'user_cal_sender', 
                  'user_cal_sender_nombre', 'user_cal_sender_apellido', 'created_at']

class TrabajoDetailSerializer(serializers.ModelSerializer):
    usuario = UsuarioSortSerializer(read_only=True)
    
    profesional = UsuarioSortSerializer(read_only=True)
    
    servicios = TrabajoServicioDetailSerializer(source='trabajo_servicios', many=True, read_only=True)
    localizacion_detalle = LocalizacionSerializer(source='localizacion', read_only=True)

    calificaciones = CalificacionDetailSerializer(many=True, read_only=True)
    
    disponibilidad_fecha_inicio = serializers.DateTimeField(source='disponibilidad.fecha_inicio', read_only=True)
    disponibilidad_fecha_fin = serializers.DateTimeField(source='disponibilidad.fecha_fin', read_only=True)
    
    class Meta:
        model = Trabajo
        fields = [
            'id', 'usuario', 'profesional',
            'descripcion', 'esUrgente', 'status', 
            'fecha_inicio', 'fecha_fin', 'precio_final',
            'servicios', 'calificaciones',
            'disponibilidad_fecha_inicio', 'disponibilidad_fecha_fin',
            'created_at', 'updated_at', 'localizacion_detalle'
        ]
    
class TrabajoListSerializer(serializers.ModelSerializer):
    usuario = UsuarioSerializer(read_only=True)
    profesional = UsuarioSerializer(read_only=True)
    calificaciones = CalificacionDetailSerializer(many=True, read_only=True)
    servicios = serializers.SerializerMethodField()
    cantidad_servicios = serializers.IntegerField(
        source='trabajo_servicios.count',
        read_only=True
    )

    localizacion_detalle = LocalizacionSerializer(
        source='localizacion',
        read_only=True
    )

    class Meta:
        model = Trabajo
        fields = [
            'id',
            'usuario',
            'profesional',
            'servicios',
            'cantidad_servicios',
            'descripcion',
            'status',
            'calificaciones',
            'precio_final',
            'fecha_inicio',
            'created_at',
            'localizacion_detalle'
        ]
    
    def get_cantidad_servicios(self, obj):
        return obj.trabajo_servicios.count()
    
    def get_servicios(self, obj):
        servicios = Servicio.objects.filter(
            trabajoservicio__trabajo=obj
        )
        return ServicioSerializer(servicios, many=True).data


class TrabajoCreateSerializer(serializers.Serializer):
    descripcion = serializers.CharField(required=True)
    profesion_id = serializers.IntegerField(required=True)
    latitud = serializers.DecimalField(max_digits=10, decimal_places=7, required=True)
    longitud = serializers.DecimalField(max_digits=10, decimal_places=7, required=True)
    direccion = serializers.CharField(required=False, allow_blank=True)


class OfertaTrabajoSerializer(serializers.ModelSerializer):
    profesional_detalle = UsuarioBasicInformationSerializer(source='profesional', read_only=True)
    
    class Meta:
        model = OfertaTrabajo
        fields = ['id', 'trabajo', 'profesional', 'profesional_detalle', 
                  'precio_ofertado', 'tiempo_estimado', 'mensaje', 'status', 
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'trabajo', 'profesional', 'status', 'created_at', 'updated_at']


class OfertaTrabajoCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfertaTrabajo
        fields = ['precio_ofertado', 'tiempo_estimado', 'mensaje']
    
    def validate_precio_ofertado(self, value):
        if value <= 0:
            raise serializers.ValidationError("El precio debe ser mayor a 0")
        return value
    
    def validate_tiempo_estimado(self, value):
        if value <= 0:
            raise serializers.ValidationError("El tiempo estimado debe ser mayor a 0")
        return value


class TrabajoUrgenteDetailSerializer(serializers.ModelSerializer):
    usuario = UsuarioBasicInformationSerializer(read_only=True)
    profesional = UsuarioBasicInformationSerializer(read_only=True)
    localizacion_detalle = LocalizacionSerializer(source='localizacion', read_only=True)
    profesion_detalle = ProfesionSerializer(source='profesion_urgente', read_only=True)
    ofertas = OfertaTrabajoSerializer(many=True, read_only=True)
    cantidad_ofertas = serializers.SerializerMethodField()
    
    class Meta:
        model = Trabajo
        fields = ['id', 'usuario', 'profesional', 'descripcion', 'status', 
                  'precio_final', 'esUrgente', 'localizacion_detalle', 
                  'profesion_detalle', 'ofertas', 'fecha_inicio', 
                  'cantidad_ofertas', 'created_at', 'updated_at']
    
    def get_cantidad_ofertas(self, obj):
        return obj.ofertas.count()
