from rest_framework import serializers
from .models import UsuarioLocalizacion
from localizacion.serializers import LocalizacionSerializer


class UsuarioLocalizacionSerializer(serializers.ModelSerializer):
    localizacion_detalle = LocalizacionSerializer(source='localizacion', read_only=True)
    
    class Meta:
        model = UsuarioLocalizacion
        fields = ['id', 'usuario', 'localizacion', 'localizacion_detalle', 'es_principal', 'created_at', 'updated_at']
        read_only_fields = ['id', 'usuario', 'created_at', 'updated_at']


class UsuarioLocalizacionCreateSerializer(serializers.Serializer):
    ubicacion = serializers.CharField(required=False, allow_blank=True, max_length=255)
    latitud = serializers.DecimalField(max_digits=10, decimal_places=7, required=True)
    longitud = serializers.DecimalField(max_digits=10, decimal_places=7, required=True)
    address = serializers.CharField(required=False, allow_blank=True)
    notas = serializers.CharField(required=False, allow_blank=True)
    interior_door = serializers.CharField(required=False, allow_blank=True, max_length=50)
    city = serializers.CharField(required=False, allow_blank=True, max_length=100)
    country = serializers.CharField(required=False, allow_blank=True, max_length=100)
    county = serializers.CharField(required=False, allow_blank=True, max_length=100)
    state = serializers.CharField(required=False, allow_blank=True, max_length=100)
    es_principal = serializers.BooleanField(required=False, default=False)
