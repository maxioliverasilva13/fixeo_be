from rest_framework import serializers
from .models import Profesion


class ProfesionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profesion
        fields = ['id', 'nombre', 'descripcion', 'logo_svg_url']
        read_only_fields = ['id']
