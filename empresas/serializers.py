from rest_framework import serializers
from servicios.serializers import ServicioSerializer
from .models import Empresa, Producto
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
            'company_type',
            'created_at',
            'updated_at',
        ]

class ProductoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Producto
        fields = ['id', 'nombre', 'descripcion', 'precio', 'stock', 'disponible', 'foto_url', 'empresa', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

