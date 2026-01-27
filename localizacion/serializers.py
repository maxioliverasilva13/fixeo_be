from rest_framework import serializers
from .models import Localizacion


class LocalizacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Localizacion
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
