from rest_framework import serializers

from .models import Cupon


class CuponSerializer(serializers.ModelSerializer):
    estado = serializers.CharField(read_only=True)
    fecha_creacion = serializers.DateTimeField(source='created_at', read_only=True)
    orden_id = serializers.PrimaryKeyRelatedField(source='orden', read_only=True)
    trabajo_id = serializers.PrimaryKeyRelatedField(source='trabajo', read_only=True)

    class Meta:
        model = Cupon
        fields = [
            'id', 'codigo', 'empresa', 'cliente', 'tipo_descuento', 'valor',
            'estado', 'fecha_creacion', 'fecha_expiracion', 'fecha_uso',
            'orden_id', 'trabajo_id',
        ]
        read_only_fields = fields


class CrearCuponSerializer(serializers.Serializer):
    cliente_id = serializers.IntegerField()
    tipo_descuento = serializers.ChoiceField(choices=Cupon.TipoDescuento.choices)
    valor = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)
    fecha_expiracion = serializers.DateField(required=False, allow_null=True)

    def validate(self, attrs):
        if attrs['tipo_descuento'] == Cupon.TipoDescuento.PORCENTAJE and not (0 < attrs['valor'] <= 100):
            raise serializers.ValidationError('El porcentaje debe estar entre 1 y 100.')
        return attrs


class ValidarCuponSerializer(serializers.Serializer):
    codigo = serializers.CharField(max_length=20)
    empresa_id = serializers.IntegerField()
    cliente_id = serializers.IntegerField()
