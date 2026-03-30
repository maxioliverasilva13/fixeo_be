from rest_framework import serializers
from .models import Carrito, CarritoItem, Orden, OrdenItem


class CarritoItemSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    producto_precio = serializers.DecimalField(source='producto.precio', max_digits=10, decimal_places=2, read_only=True)
    producto_agotado = serializers.BooleanField(source='producto.agotado', read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    
    class Meta:
        model = CarritoItem
        fields = ['id', 'carrito', 'producto', 'producto_nombre', 'producto_precio', 
                  'producto_agotado', 'cantidad', 'precio_unitario', 'subtotal', 'created_at']
        read_only_fields = ['id', 'carrito', 'precio_unitario', 'created_at']

    def validate_producto(self, value):
        if value.agotado:
            raise serializers.ValidationError("Este producto está agotado")
        return value


class CarritoSerializer(serializers.ModelSerializer):
    items = CarritoItemSerializer(many=True, read_only=True)
    total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    cantidad_items = serializers.IntegerField(read_only=True)
    empresa_nombre = serializers.CharField(source='empresa.nombre', read_only=True)
    
    class Meta:
        model = Carrito
        fields = ['id', 'usuario', 'empresa', 'empresa_nombre', 'activo', 'items', 
                  'total', 'cantidad_items', 'created_at', 'updated_at']
        read_only_fields = ['id', 'usuario', 'activo', 'created_at', 'updated_at']


class CarritoItemCreateSerializer(serializers.Serializer):
    producto_id = serializers.IntegerField(required=True)
    cantidad = serializers.IntegerField(required=True, min_value=1)


class OrdenItemSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    producto_codigo = serializers.CharField(source='producto.codigo', read_only=True)
    
    class Meta:
        model = OrdenItem
        fields = ['id', 'orden', 'producto', 'producto_nombre', 'producto_codigo', 
                  'cantidad', 'precio_unitario', 'subtotal']
        read_only_fields = ['id', 'orden']


class OrdenSerializer(serializers.ModelSerializer):
    items = OrdenItemSerializer(many=True, read_only=True)
    usuario_nombre = serializers.SerializerMethodField()
    empresa_nombre = serializers.CharField(source='empresa.nombre', read_only=True)
    localizacion_info = serializers.SerializerMethodField()
    pago_info = serializers.SerializerMethodField()
    
    class Meta:
        model = Orden
        fields = ['id', 'numero_orden', 'usuario', 'usuario_nombre', 'empresa', 'empresa_nombre',
                  'status', 'metodo_pago', 'tipo_entrega', 'localizacion_entrega', 'localizacion_info',
                  'total', 'comision_plataforma', 'pago_status', 'notas', 'fecha_entrega', 'items',
                  'pago_info', 'created_at', 'updated_at', 'curreny']
        read_only_fields = ['id', 'numero_orden', 'usuario', 'total', 'comision_plataforma',
                            'pago_status', 'localizacion_entrega', 'created_at', 'updated_at']

    def get_usuario_nombre(self, obj):
        return f"{obj.usuario.nombre} {obj.usuario.apellido}"

    def get_localizacion_info(self, obj):
        if obj.localizacion_entrega:
            return {
                'address': obj.localizacion_entrega.address,
                'city': obj.localizacion_entrega.city,
                'country': obj.localizacion_entrega.country,
                'interior_door': obj.localizacion_entrega.interior_door,
                'notas': obj.localizacion_entrega.notas,
            }
        return None

    def get_pago_info(self, obj):
        if obj.metodo_pago != 'mercadopago':
            return None
        pago = obj.pagos.order_by('-created_at').first() if hasattr(obj, 'pagos') else None
        if not pago:
            return None
        return {
            'pago_id': pago.id,
            'status': pago.status,
            'mp_status': pago.mp_status,
            'mp_preference_id': pago.mp_preference_id,
            'monto': str(pago.monto),
            'comision': str(pago.comision_plataforma),
        }


class OrdenCreateSerializer(serializers.Serializer):
    metodo_pago = serializers.ChoiceField(choices=Orden.METODO_PAGO_CHOICES, required=True)
    tipo_entrega = serializers.ChoiceField(choices=Orden.TIPO_ENTREGA_CHOICES, required=True)
    notas = serializers.CharField(required=False, allow_blank=True)

    card_token = serializers.CharField(required=False, allow_blank=True, default='')
    payment_method_id = serializers.CharField(required=False, allow_blank=True, default='')
    payment_method_type = serializers.CharField(required=False, allow_blank=True, default='')
    issuer_id = serializers.CharField(required=False, allow_blank=True, default='')
    installments = serializers.IntegerField(required=False, default=1)
    bin = serializers.CharField(required=False, allow_blank=True, default='',
                                help_text='Primeros 6 dígitos de la tarjeta')
    is_saved_card = serializers.BooleanField(required=False, default=False)
    tarjeta_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    currency = serializers.ChoiceField(
        choices=['ARS', 'BRL', 'CLP', 'COP', 'MXN', 'PEN', 'UYU', 'BOB', 'PYG', 'VES', 'CRC', 'DOP', 'GTQ', 'HNL', 'NIO', 'PAB', 'USD'],
        required=False,
        allow_null=True,
        default=None
    )

    def validate(self, data):
        if data['metodo_pago'] == 'mercadopago' and not data.get('card_token'):
            raise serializers.ValidationError(
                {"card_token": "Requerido para pagos con MercadoPago."}
            )
        if data.get('is_saved_card') and not data.get('tarjeta_id'):
            raise serializers.ValidationError(
                {"tarjeta_id": "Requerido cuando is_saved_card es true."}
            )
        return data
