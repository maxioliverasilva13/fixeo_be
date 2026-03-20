from rest_framework import serializers
from servicios.serializers import ServicioSerializer
from .models import Empresa, CategoriaProducto, Producto
from localizacion.serializers import LocalizacionSerializer


class EmpresaSerializer(serializers.ModelSerializer):
    trabajo_domicilio = serializers.BooleanField(source='admin_id.trabajo_domicilio', read_only=True)
    trabajo_local = serializers.BooleanField(source='admin_id.trabajo_local', read_only=True)
    efectivo_disponible = serializers.SerializerMethodField()
    metodos_pago_disponibles = serializers.SerializerMethodField()

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
            'acepta_efectivo',
            'acepta_tarjeta',
            'efectivo_disponible',
            'metodos_pago_disponibles',
            'trabajo_domicilio',
            'trabajo_local',
            'created_at',
            'updated_at',
        ]

    def get_efectivo_disponible(self, obj):
        """
        acepta_efectivo=True solo funciona si el admin tiene suscripción activa.
        """
        if not obj.acepta_efectivo:
            return False
        from suscripciones.models import Subscripcion
        from django.utils import timezone
        return Subscripcion.objects.filter(
            user_id=obj.admin_id,
            cancelada=False,
            expiracion__gt=timezone.now(),
        ).exists()

    def get_metodos_pago_disponibles(self, obj):
        """Lista de métodos de pago que la empresa realmente puede usar."""
        metodos = []
        if obj.acepta_tarjeta:
            metodos.append('mercadopago')
        if obj.acepta_efectivo:
            from suscripciones.models import Subscripcion
            from django.utils import timezone
            tiene_sub = Subscripcion.objects.filter(
                user_id=obj.admin_id,
                cancelada=False,
                expiracion__gt=timezone.now(),
            ).exists()
            if tiene_sub:
                metodos.append('efectivo')
        return metodos


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
