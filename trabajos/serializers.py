from rest_framework import serializers
from .models import Trabajo, Calificacion, Estados


class EstadosSerializer(serializers.ModelSerializer):
    class Meta:
        model = Estados
        fields = '__all__'


class CalificacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Calificacion
        fields = '__all__'


class TrabajoSerializer(serializers.ModelSerializer):
    estados = EstadosSerializer(many=True, read_only=True)
    calificaciones = CalificacionSerializer(many=True, read_only=True)
    
    class Meta:
        model = Trabajo
        fields = '__all__'

