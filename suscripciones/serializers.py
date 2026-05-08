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


class SubscripcionCreateSerializer(serializers.ModelSerializer):
    """Usado al crear una suscripción: auto-asigna jobs_restantes desde el plan."""

    class Meta:
        model = Subscripcion
        fields = ['plan_id', 'user_id', 'expiracion']

    def create(self, validated_data):
        plan = validated_data['plan_id']
        validated_data['jobs_restantes'] = plan.cantidad_jobs
        return super().create(validated_data)

class UsuarioSubscripcionActivaSerializer(serializers.ModelSerializer):
    plan_detalle = PlanSerializer(source='plan_id', read_only=True)
    jobs_restantes = serializers.SerializerMethodField()

    class Meta:
        model = Subscripcion
        fields = [
            'id',
            'plan_detalle',
            'jobs_restantes',
            'expiracion',
            'cancelada',
            'source',
            'status',
        ]

    def get_jobs_restantes(self, obj):
        return self.context.get('jobs_restantes', obj.jobs_restantes)