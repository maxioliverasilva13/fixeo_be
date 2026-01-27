from rest_framework import serializers
from .models import Disponibilidad


class DisponibilidadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Disponibilidad
        fields = '__all__'
        read_only_fields = ['id']
