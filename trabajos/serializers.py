from rest_framework import serializers
from .models import Trabajo, Calificacion

from rest_framework import serializers
from .models import Trabajo, Calificacion, TrabajoServicio
from usuario.serializers import UsuarioSerializer, UsuarioSortSerializer 
from servicios.serializers import ServicioSerializer 
from profesion.serializers import ProfesionSerializer 
from usuario.serializers import UsuarioBasicInformationSerializer
from localizacion.serializers import LocalizacionSerializer


class CalificacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Calificacion
        fields = '__all__'


class TrabajoSerializer(serializers.ModelSerializer):
    calificaciones = CalificacionSerializer(many=True, read_only=True)
    
    class Meta:
        model = Trabajo
        fields = '__all__'

class TrabajoCreateSerializer(serializers.ModelSerializer):
    servicios_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True
    )
    fecha = serializers.DateField(write_only=True)
    hora = serializers.TimeField(write_only=True)
    profesional_id = serializers.IntegerField(write_only=True)
    es_domicilio_profesional = serializers.BooleanField(write_only=True)

    class Meta:
        model = Trabajo
        fields = [
            'descripcion', 'esUrgente',
            'servicios_ids', 'fecha', 'hora', 'profesional_id', 'es_domicilio_profesional'
        ]

    def validate_servicios_ids(self, value):
        if not value:
            raise serializers.ValidationError("Se debe enviar al menos un servicio")
        if not all(isinstance(i, int) for i in value):
            raise serializers.ValidationError("Todos los IDs de servicios deben ser enteros")
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

# Serializer completo para ver detalles de un trabajo
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
    usuario_nombre = serializers.CharField(source='usuario.nombre', read_only=True)
    profesional_nombre = serializers.CharField(source='profesional.nombre', read_only=True)
    cantidad_servicios = serializers.SerializerMethodField()
    localizacion_detalle = LocalizacionSerializer(source='localizacion', read_only=True)
    
    class Meta:
        model = Trabajo
        fields = [
            'id', 'usuario_nombre', 'profesional_nombre',
            'descripcion', 'status', 'precio_final',
            'fecha_inicio', 'cantidad_servicios', 'created_at', 'localizacion_detalle'
        ]
        