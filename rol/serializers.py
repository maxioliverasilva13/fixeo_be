from rest_framework import serializers
from .models import Rol


class RolSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rol
        fields = ['id', 'nombre']
        read_only_fields = ['id']
