from rest_framework import serializers
from .models import MercadoPagoCustomer, Pago, Tarjeta


class PagoSerializer(serializers.ModelSerializer):
    entidad_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Pago
        fields = [
            'id', 'tipo', 'orden', 'trabajo', 'usuario',
            'monto', 'comision_plataforma', 'monto_vendedor',
            'mp_preference_id', 'mp_order_id', 'mp_payment_id',
            'mp_status', 'mp_status_detail',
            'status', 'liberado_at', 'entidad_id',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'mp_preference_id', 'mp_order_id', 'mp_payment_id',
            'mp_status', 'mp_status_detail', 'status', 'liberado_at',
            'created_at', 'updated_at',
        ]


class PagoResumenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pago
        fields = [
            'id', 'tipo', 'monto', 'comision_plataforma', 'monto_vendedor',
            'mp_preference_id', 'status', 'mp_status', 'created_at',
        ]


class TarjetaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tarjeta
        fields = [
            'id', 'mp_card_id', 'last_four', 'brand',
            'expiration_month', 'expiration_year',
            'payment_method_id', 'payment_type', 'issuer_id', 'created_at',
        ]
        read_only_fields = fields


class GuardarTarjetaSerializer(serializers.Serializer):
    card_token = serializers.CharField(required=True)


class PagoDirectoSerializer(serializers.Serializer):
    card_token = serializers.CharField(required=True)
    payment_method_id = serializers.CharField(required=False, default='', allow_blank=True)
    payment_method_type = serializers.CharField(required=False, default='', allow_blank=True)
    issuer_id = serializers.CharField(required=False, default='', allow_blank=True)
    installments = serializers.IntegerField(required=False, default=1)
    bin = serializers.CharField(required=False, default='', allow_blank=True,
                                help_text='Primeros 6 dígitos de la tarjeta')
    is_saved_card = serializers.BooleanField(required=False, default=False)
    tarjeta_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    tipo = serializers.ChoiceField(choices=['orden', 'trabajo'], required=True)
    orden_id = serializers.IntegerField(required=False, allow_null=True)
    trabajo_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, data):
        if data['tipo'] == 'orden' and not data.get('orden_id'):
            raise serializers.ValidationError("orden_id requerido para tipo 'orden'")
        if data['tipo'] == 'trabajo' and not data.get('trabajo_id'):
            raise serializers.ValidationError("trabajo_id requerido para tipo 'trabajo'")
        if data.get('is_saved_card') and not data.get('tarjeta_id'):
            raise serializers.ValidationError("tarjeta_id requerido cuando is_saved_card es true")
        return data
