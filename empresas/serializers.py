from rest_framework import serializers
from servicios.serializers import ServicioSerializer
from .models import Empresa
from localizacion.serializers import LocalizacionSerializer

class EmpresaSerializer(serializers.ModelSerializer):
    servicios = ServicioSerializer(many=True, read_only=True)
    localizacion_detalle = LocalizacionSerializer(source='localizacion', read_only=True)
    
    class Meta:
        model = Empresa
        fields = '__all__'
