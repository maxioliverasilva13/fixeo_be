from rest_framework import serializers
from .models import Plan, Subscripcion


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = '__all__'


class SubscripcionSerializer(serializers.ModelSerializer):
    plan_detalle = PlanSerializer(source='plan_id', read_only=True)
    
    class Meta:
        model = Subscripcion
        fields = '__all__'

