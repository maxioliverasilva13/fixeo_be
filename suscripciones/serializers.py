from rest_framework import serializers
from .models import Plan, Subscripcion, CampanaMarketing


class PlanSerializer(serializers.ModelSerializer):
    precio_tachado = serializers.SerializerMethodField()
    campana_mensaje = serializers.SerializerMethodField()

    class Meta:
        model = Plan
        fields = '__all__'

    def get_precio_tachado(self, obj):
        campana = self.context.get('campana_activa')
        if campana and campana.plan_id == obj.id:
            return str(obj.precio)
        return None

    def get_campana_mensaje(self, obj):
        campana = self.context.get('campana_activa')
        if not campana or campana.plan_id != obj.id:
            return None
        if campana.mensaje_promocional:
            return campana.mensaje_promocional
        if campana.cupo_usuarios:
            return f"Por ser uno de los primeros {campana.cupo_usuarios} clientes"
        return None


class PlanAdminSerializer(serializers.ModelSerializer):
    """Serializer de escritura para el CRUD de Planes del admin: solo los
    campos reales del modelo (precio_tachado/campana_mensaje son calculados
    por campaña, no se editan acá)."""

    class Meta:
        model = Plan
        fields = [
            'id', 'nombre', 'descripcion', 'precio', 'cantidad_personas',
            'duracion', 'google_play_id', 'appstore_id',
            'caracteristicas', 'activo', 'tiene_landing_page', 'recomendado',
            'badge_mapa_url', 'user_badge_url', 'color', 'slogan',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CampanaMarketingSerializer(serializers.ModelSerializer):
    esta_vigente = serializers.SerializerMethodField()
    usuarios_inscriptos = serializers.SerializerMethodField()
    plan_detalle = PlanSerializer(source='plan', read_only=True)

    class Meta:
        model = CampanaMarketing
        fields = [
            'id', 'nombre', 'plan', 'plan_detalle', 'fecha_inicio', 'duracion', 'dias_gratis',
            'mensaje_promocional', 'cupo_usuarios', 'activa',
            'esta_vigente', 'usuarios_inscriptos', 'created_at', 'updated_at',
        ]

    def get_esta_vigente(self, obj):
        return obj.esta_vigente()

    def get_usuarios_inscriptos(self, obj):
        return obj.usuarios_inscriptos()

class CampanaUsuarioInscriptoUsuarioSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()
    apellido = serializers.CharField()
    correo = serializers.CharField()


class CampanaUsuarioInscriptoSerializer(serializers.ModelSerializer):
    """Una fila por Subscripcion otorgada por la campaña (usuario + fecha de alta)."""
    usuario = CampanaUsuarioInscriptoUsuarioSerializer(source='user_id', read_only=True)

    class Meta:
        model = Subscripcion
        fields = ['id', 'usuario', 'created_at']


class SubscripcionSerializer(serializers.ModelSerializer):
    plan_detalle = PlanSerializer(source='plan_id', read_only=True)

    class Meta:
        model = Subscripcion
        fields = '__all__'


class SubscripcionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscripcion
        fields = ['plan_id', 'user_id', 'expiracion']

class UsuarioSubscripcionActivaSerializer(serializers.ModelSerializer):
    plan_detalle = PlanSerializer(source='plan_id', read_only=True)

    class Meta:
        model = Subscripcion
        fields = [
            'id',
            'plan_detalle',
            'expiracion',
            'cancelada',
            'source',
            'status',
        ]