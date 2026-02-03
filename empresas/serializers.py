from rest_framework import serializers
from servicios.serializers import ServicioSerializer
from .models import Empresa
from localizacion.serializers import LocalizacionSerializer

class EmpresaSerializer(serializers.ModelSerializer):

    class Meta:
        model = Empresa
        fields = [
            'id',
            'nombre',
            'ubicacion',
            'descripcion',
            'latitud',
            'longitud',
            'unipersonal',
            'created_at',
            'updated_at',
        ]

