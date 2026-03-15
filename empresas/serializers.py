from rest_framework import serializers
from servicios.serializers import ServicioSerializer
from .models import Empresa, CategoriaProducto, Producto
from localizacion.serializers import LocalizacionSerializer

class EmpresaSerializer(serializers.ModelSerializer):
    trabajo_domicilio = serializers.BooleanField(source='admin_id.trabajo_domicilio', read_only=True)
    trabajo_local = serializers.BooleanField(source='admin_id.trabajo_local', read_only=True)

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
            'vende_productos',
            'vende_servicios',
            'trabajo_domicilio',
            'trabajo_local',
            'created_at',
            'updated_at',
        ]


class CategoriaProductoSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = CategoriaProducto
        fields = ['id', 'nombre', 'descripcion', 'empresa', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductoSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.CharField(source='categoria.nombre', read_only=True)
    
    class Meta:
        model = Producto
        fields = ['id', 'nombre', 'descripcion', 'precio', 'codigo', 'agotado', 'foto', 
                  'empresa', 'categoria', 'categoria_nombre', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
