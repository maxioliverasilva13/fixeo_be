from rest_framework import serializers
from .models import DeviceToken, Notificaciones, Notas


class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = '__all__'

class DeviceTokenCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = ['device_name', 'device_token']


class NotificacionesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notificaciones
        fields = '__all__'


class NotasSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notas
        fields = '__all__'

