from rest_framework import serializers
from .models import Servicio
from profesion.serializers import ProfesionSerializer


class ServicioSerializer(serializers.ModelSerializer):
    profesion_detalle = ProfesionSerializer(source='profesion', read_only=True)
    
    class Meta:
        model = Servicio
        fields = ['id', 'usuario', 'profesion', 'profesion_detalle', 'precio', 'divisa', 'tiempo', 'notas', 'created_at', 'updated_at']
        read_only_fields = ['id', 'usuario', 'created_at', 'updated_at']


class ServicioCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Servicio
        fields = ['profesion', 'precio', 'divisa', 'tiempo', 'notas']
    
    def validate_precio(self, value):
        if value <= 0:
            raise serializers.ValidationError("El precio debe ser mayor a 0")
        return value
    
    def validate_tiempo(self, value):
        if value <= 0:
            raise serializers.ValidationError("El tiempo debe ser mayor a 0")
        return value
