from rest_framework import serializers

from .models import ZonaNoTrabajo
from .zonas_utils import validar_zona_dentro_cobertura


class ZonaNoTrabajoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ZonaNoTrabajo
        fields = [
            'id',
            'nombre',
            'latitud',
            'longitud',
            'radio_km',
            'activa',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        request = self.context.get('request')
        usuario = request.user if request else None
        if not usuario:
            return attrs

        instance = getattr(self, 'instance', None)
        latitud = attrs.get('latitud', getattr(instance, 'latitud', None))
        longitud = attrs.get('longitud', getattr(instance, 'longitud', None))
        radio_km = attrs.get('radio_km', getattr(instance, 'radio_km', None))

        if latitud is None or longitud is None or radio_km is None:
            raise serializers.ValidationError('Latitud, longitud y radio son obligatorios.')

        error = validar_zona_dentro_cobertura(usuario, latitud, longitud, radio_km)
        if error:
            raise serializers.ValidationError(error)

        return attrs

    def create(self, validated_data):
        validated_data['usuario'] = self.context['request'].user
        return super().create(validated_data)
