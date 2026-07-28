from rest_framework import serializers
from .models import Publicidad


class PublicidadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Publicidad
        fields = '__all__'
