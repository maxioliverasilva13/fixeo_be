from rest_framework import serializers
from .models import Empresa, Horarios, Servicios
from localizacion.serializers import LocalizacionSerializer


class HorariosSerializer(serializers.ModelSerializer):
    class Meta:
        model = Horarios
        fields = '__all__'


class ServiciosSerializer(serializers.ModelSerializer):
    class Meta:
        model = Servicios
        fields = '__all__'


class EmpresaSerializer(serializers.ModelSerializer):
    horarios = HorariosSerializer(many=True, read_only=True)
    servicios = ServiciosSerializer(many=True, read_only=True)
    localizacion_detalle = LocalizacionSerializer(source='localizacion', read_only=True)
    
    class Meta:
        model = Empresa
        fields = '__all__'

