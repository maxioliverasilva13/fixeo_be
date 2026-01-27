from rest_framework import serializers
from .models import UsuarioProfesion
from profesion.serializers import ProfesionSerializer


class UsuarioProfesionSerializer(serializers.ModelSerializer):
    profesion = ProfesionSerializer(read_only=True)
    
    class Meta:
        model = UsuarioProfesion
        fields = ['id', 'profesion', 'usuario']
        read_only_fields = ['id']
