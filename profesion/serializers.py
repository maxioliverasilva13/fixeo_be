from rest_framework import serializers
from .models import Profesion


class ProfesionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profesion
        fields = ['id', 'nombre', 'descripcion', 'logo_svg_url', 'estado']
        read_only_fields = ['id']


class ProponerProfesionSerializer(serializers.Serializer):
    nombre = serializers.CharField(required=True, max_length=100, allow_blank=False)
