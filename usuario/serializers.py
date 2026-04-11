from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import Usuario
from .utils import foto_usuario_api
from rol.serializers import RolSerializer
from django.db.models import Prefetch
from empresas.serializers import EmpresaSerializer
from localizacion.models import Localizacion
from django.db import transaction
from datetime import timedelta


class UsuarioFotoApiMixin:
    """foto_url y rounded_foto_url siempre como string; vacío si el usuario no tiene foto."""

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if 'foto_url' in data:
            data['foto_url'] = foto_usuario_api(data.get('foto_url'))
        if 'rounded_foto_url' in data:
            data['rounded_foto_url'] = foto_usuario_api(data.get('rounded_foto_url'))
        return data


class UsuarioSortSerializer(UsuarioFotoApiMixin, serializers.ModelSerializer):
    rol_detalle = RolSerializer(source='rol', read_only=True)
    empresa = serializers.SerializerMethodField()
    localizacion_principal = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = ['id', 'correo', 'nombre', 'apellido', 'telefono', 'foto_url', 'rounded_foto_url', 
                  'trabajo_domicilio', 'trabajo_local', 'is_owner_empresa', 
                  'is_active','empresa', 'rango_mapa_km', 'created_at', 'updated_at', 'rol', 'rol_detalle',
                  'is_configured', 'auto_aprobacion_trabajos', 'localizacion_principal']
        read_only_fields = ['id', 'created_at', 'updated_at']


    def get_empresa(self, obj):
        if not obj.is_owner_empresa:
            return None

        empresa = obj.empresas_administradas.first()
        if not empresa:
            return None

        return EmpresaSerializer(empresa).data
    def get_localizacion_principal(self, obj):
            relacion = obj.localizaciones.filter(localizacion__isPrimary=True).select_related('localizacion').first()
            
            if not relacion:
                return None
            
            from usuario_localizacion.serializers import LocalizacionSerializer
            return LocalizacionSerializer(relacion.localizacion).data


class UsuarioSerializer(UsuarioFotoApiMixin, serializers.ModelSerializer):
    profesiones = serializers.SerializerMethodField()
    localizaciones = serializers.SerializerMethodField()
    servicios = serializers.SerializerMethodField()
    empresa = serializers.SerializerMethodField()
    rol_detalle = RolSerializer(source='rol', read_only=True)
    foto_map_url = serializers.SerializerMethodField()
    localizacion_principal = serializers.SerializerMethodField()
    device_tokens = serializers.SerializerMethodField()
    subscripcion_activa = serializers.SerializerMethodField()
    es_visible_en_mapa = serializers.SerializerMethodField()
    advertencias_mapa = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = ['id', 'correo', 'nombre', 'apellido', 'telefono', 'foto_url', 'rounded_foto_url', 'foto_map_url',
                  'trabajo_domicilio', 'trabajo_local', 'is_owner_empresa',
                  'is_active', 'defaultMessageReservation', 'rango_mapa_km', 'created_at', 'updated_at', 'rol', 'rol_detalle', 'empresa',
                  'profesiones', 'localizaciones', 'localizacion_principal', 'servicios', 'is_configured',
                  'auto_aprobacion_trabajos', 'device_tokens',
                  'subscripcion_activa', 'rating','cant_calif',
                  'es_visible_en_mapa', 'advertencias_mapa']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_subscripcion_activa(self, obj):
        if not obj.is_owner_empresa:
            return None

        from django.utils import timezone
        from suscripciones.models import Subscripcion
        from suscripciones.serializers import UsuarioSubscripcionActivaSerializer
        from trabajos.models import Trabajo

        subscripcion = (
            Subscripcion.objects
            .filter(
                user_id=obj,
                cancelada=False,
                expiracion__gt=timezone.now(),
            )
            .select_related('plan_id')
            .order_by('-created_at')
            .first()
        )

        if not subscripcion:
            return None

        inicio_periodo = subscripcion.expiracion - timedelta(days=30)

        trabajos_usados = Trabajo.objects.filter(
            profesional=obj,
            metodo_pago='efectivo',
            created_at__gte=inicio_periodo,
            is_deleted=False,
        ).exclude(status='cancelado').count()

        cantidad_jobs = subscripcion.plan_id.cantidad_jobs
        jobs_restantes = max(0, cantidad_jobs - trabajos_usados)

        return UsuarioSubscripcionActivaSerializer(subscripcion, context={
            'jobs_restantes': jobs_restantes
        }).data

    def _get_empresa_visibilidad(self, obj):
        """
        Devuelve (es_visible, [advertencias]).
        Solo aplica a propietarios de empresa; devuelve (None, []) para el resto.
        """
        if not obj.is_owner_empresa:
            return None, []

        empresa = obj.empresas_administradas.first()
        if not empresa:
            return False, ['No tenés empresa configurada']

        from django.utils import timezone
        from datetime import timedelta
        from suscripciones.models import Subscripcion
        from trabajos.models import Trabajo

        # MercadoPago disponible
        has_mp = empresa.acepta_tarjeta and empresa.is_mercadopago_vinculado

        has_efectivo = False
        advertencias = []

        if empresa.acepta_efectivo:
            subscripcion = (
                Subscripcion.objects
                .filter(user_id=obj, cancelada=False, expiracion__gt=timezone.now())
                .select_related('plan_id')
                .order_by('-created_at')
                .first()
            )
            if subscripcion:
                inicio_periodo = subscripcion.expiracion - timedelta(days=30)
                usados = Trabajo.objects.filter(
                    profesional=obj,
                    metodo_pago='efectivo',
                    created_at__gte=inicio_periodo,
                    is_deleted=False,
                ).exclude(status='cancelado').count()
                jobs_restantes = max(0, subscripcion.plan_id.cantidad_jobs - usados)
                if jobs_restantes > 0:
                    has_efectivo = True
                else:
                    advertencias.append(
                        'Alcanzaste el límite de trabajos en efectivo de tu suscripción'
                    )
            else:
                advertencias.append('No tenés suscripción activa para cobrar en efectivo')

        if empresa.acepta_tarjeta and not empresa.is_mercadopago_vinculado:
            advertencias.append('Vinculá tu cuenta de MercadoPago para cobrar con tarjeta')

        if has_mp or has_efectivo:
            return True, []

        return False, advertencias if advertencias else ['No tenés ningún método de pago disponible']

    def get_es_visible_en_mapa(self, obj):
        if not hasattr(self, '_visibilidad_cache'):
            self._visibilidad_cache = {}
        if obj.id not in self._visibilidad_cache:
            self._visibilidad_cache[obj.id] = self._get_empresa_visibilidad(obj)
        visible, _ = self._visibilidad_cache[obj.id]
        return visible

    def get_advertencias_mapa(self, obj):
        if not hasattr(self, '_visibilidad_cache'):
            self._visibilidad_cache = {}
        if obj.id not in self._visibilidad_cache:
            self._visibilidad_cache[obj.id] = self._get_empresa_visibilidad(obj)
        _, advertencias = self._visibilidad_cache[obj.id]
        return advertencias
    
    def get_profesiones(self, obj):
        from profesion.serializers import ProfesionSerializer
        usuario_profesiones = obj.usuario_profesiones.all()
        return [ProfesionSerializer(up.profesion).data for up in usuario_profesiones]

    def get_foto_map_url(self, obj):
        return foto_usuario_api(obj.rounded_foto_url or obj.foto_url)

    def get_localizaciones(self, obj):
        from usuario_localizacion.serializers import UsuarioLocalizacionSerializer
        usuario_localizaciones = obj.localizaciones.select_related('localizacion').all()
        return UsuarioLocalizacionSerializer(usuario_localizaciones, many=True).data

    def get_servicios(self, obj):
        if obj.is_owner_empresa:
            from servicios.serializers import ServicioSerializer
            servicios = obj.servicios.select_related('profesion').all()
            return ServicioSerializer(servicios, many=True).data
        return []

    def get_empresa(self, obj):
        if not obj.is_owner_empresa:
            return None
        from empresas.serializers import EmpresaSerializer
        empresa = obj.empresas_administradas.first()
        if not empresa:
            return None
        return EmpresaSerializer(empresa).data

    def get_localizacion_principal(self, obj):
        from usuario_localizacion.serializers import UsuarioLocalizacionSerializer
        loc_principal = (
            obj.localizaciones
            .select_related('localizacion')
            .filter(localizacion__isPrimary=True)
            .first()
        )
        if not loc_principal:
            return None
        return UsuarioLocalizacionSerializer(loc_principal).data

    def get_device_tokens(self, obj):
        return list(
            obj.device_tokens
            .filter(enabled=True)
            .values_list('device_token', flat=True)
        )

class UsuarioBasicInformationSerializer(UsuarioFotoApiMixin, serializers.ModelSerializer):
    localizacion = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = ['id', 'nombre', 'apellido', 'foto_url', 'rounded_foto_url', 'telefono', 'localizacion']

    def get_localizacion(self, obj):
        from usuario_localizacion.serializers import UsuarioLocalizacionSerializer

        usuario_localizacion = (
            obj.localizaciones
            .filter(localizacion__isPrimary=True)
            .select_related('localizacion')
            .first()
        )

        if usuario_localizacion:
            return UsuarioLocalizacionSerializer(usuario_localizacion).data

        return None

class UsuarioCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    latitude = serializers.FloatField(required=False, allow_null=True)
    longitude = serializers.FloatField(required=False, allow_null=True)
    direction_name = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Usuario
        fields = [
            'correo',
            'password',
            'password2',
            'nombre',
            'apellido',
            'telefono',
            'rounded_foto_url',
            'is_owner_empresa',
            'latitude',
            'longitude',
            'direction_name'
        ]

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Las contraseñas no coinciden."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')

        lat = validated_data.pop('latitude', None)
        lng = validated_data.pop('longitude', None)
        direction_name = validated_data.pop('direction_name', '')

        with transaction.atomic():
            from usuario_localizacion.models import UsuarioLocalizacion
            user = Usuario.objects.create_user(**validated_data)

            if lat is not None and lng is not None:
                localizacion = Localizacion.objects.create(
                    ubicacion=direction_name,
                    latitud=lat,
                    longitud=lng,
                    address=direction_name,
                    city='',
                    country='',
                    county='',
                    state='',
                    isPrimary=True
                )

                UsuarioLocalizacion.objects.create(
                    usuario=user,
                    localizacion=localizacion
                )

        return user

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password2 = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password2']:
            raise serializers.ValidationError({"new_password": "Las contraseñas no coinciden."})
        return attrs


class LoginSerializer(serializers.Serializer):
    correo = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True)


class UpdateRangoMapaSerializer(serializers.Serializer):
    rango_mapa_km = serializers.DecimalField(max_digits=5, decimal_places=2, required=True)
    
    def validate_rango_mapa_km(self, value):
        if value < 0.5:
            raise serializers.ValidationError("El rango mínimo es 0.5 km")
        if value > 50:
            raise serializers.ValidationError("El rango máximo es 50 km (tamaño de una ciudad grande)")
        return value

class ValidateEmailExistSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

class RegistroSerializer(serializers.Serializer):
    foto_url = serializers.URLField(required=False, allow_blank=True)
    rounded_foto_url = serializers.URLField(required=False, allow_blank=True)
    nombre = serializers.CharField(required=True, max_length=100)
    apellido = serializers.CharField(required=True, max_length=100)
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True, validators=[validate_password])
    es_empresa = serializers.BooleanField(required=False)
    trabajo_domicilio = serializers.BooleanField(required=False)
    telefono = serializers.CharField(required=False, allow_blank=True, max_length=20)
    trabajo_local = serializers.BooleanField(required=False)
    latitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=False, allow_null=True)
    longitude = serializers.DecimalField(max_digits=10, decimal_places=7, required=False, allow_null=True)
    direction_name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    profesion_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True
    )
    
    def validate_email(self, value):
        if Usuario.objects.filter(correo=value).exists():
            raise serializers.ValidationError("Ya existe un usuario con este correo electrónico.")
        return value
    
    def validate(self, attrs):
        if attrs.get('latitude') and not attrs.get('longitude'):
            raise serializers.ValidationError({"longitude": "La longitud es requerida cuando se proporciona la latitud."})
        if attrs.get('longitude') and not attrs.get('latitude'):
            raise serializers.ValidationError({"latitude": "La latitud es requerida cuando se proporciona la longitud."})
        
        return attrs

class FilterUsersMapaSerializer(serializers.Serializer):
    north      = serializers.DecimalField(max_digits=20, decimal_places=15)
    south      = serializers.DecimalField(max_digits=20, decimal_places=15)
    east       = serializers.DecimalField(max_digits=20, decimal_places=15)
    west       = serializers.DecimalField(max_digits=20, decimal_places=15)
    profesion_id = serializers.IntegerField(required=False, allow_null=True)
    sort_by      = serializers.ChoiceField(
        choices=['mejor_valorados', 'mas_cercanos', 'mejor_precio'],
        required=False,
        default='mejor_valorados'
    )
    max_price    = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    is_urgent    = serializers.BooleanField(required=False, default=False)


class UpdateUsuarioSerializer(UsuarioFotoApiMixin, serializers.ModelSerializer):
    """
    Serializer para actualizar la información del usuario logueado
    """
    telefono = serializers.CharField(required=False, allow_blank=True, max_length=20)
    foto_url = serializers.URLField(required=False, allow_blank=True, max_length=500)
    defaultMessageReservation = serializers.CharField(required=False, allow_blank=True, max_length=1000)
    
    class Meta:
        model = Usuario
        fields = [
            'nombre', 
            'apellido', 
            'telefono', 
            'foto_url', 
            'rounded_foto_url',
            'trabajo_domicilio', 
            'trabajo_local',
            'rango_mapa_km',
            'auto_aprobacion_trabajos',
            'defaultMessageReservation',
        ]
    
    def validate_rango_mapa_km(self, value):
        if (value is None or value == ''):
            return None
        if value and value < 0.5:
            raise serializers.ValidationError("El rango mínimo es 0.5 km")
        if value and value > 500:
            raise serializers.ValidationError("El rango máximo es 500 km")
        return value
    
    def validate(self, attrs):
        usuario = self.instance 

        if not usuario or not usuario.is_owner_empresa:
            return attrs

        trabajo_domicilio = attrs.get(
            'trabajo_domicilio',
            usuario.trabajo_domicilio
        )

        trabajo_local = attrs.get(
            'trabajo_local',
            usuario.trabajo_local
        )

        if not trabajo_domicilio and not trabajo_local:
            raise serializers.ValidationError(
                "Debe tener al menos un tipo de trabajo activo (domicilio o local)."
            )

        return attrs

class UsuarioInMapaSerializer(UsuarioFotoApiMixin, serializers.ModelSerializer):
    profesiones = serializers.SerializerMethodField()
    localizacion = serializers.SerializerMethodField()
    esta_abierta = serializers.SerializerMethodField()


    class Meta:
        model = Usuario
        fields = ['id', 'nombre', 'apellido', 'foto_url', 'rounded_foto_url', 'trabajo_domicilio', 
                  'trabajo_local', 'rango_mapa_km', 'profesiones', 'localizacion', 'esta_abierta']
        read_only_fields = ['id', 'nombre', 'apellido', 'foto_url', 'rounded_foto_url', 
                            'trabajo_domicilio', 'trabajo_local', 
                            'rango_mapa_km', 'esta_abierta']
        
    def get_profesiones(self, obj):
        from profesion.serializers import ProfesionSerializer
        usuario_profesiones = obj.usuario_profesiones.all()
        return [ProfesionSerializer(up.profesion).data for up in usuario_profesiones]
    
    def get_localizacion(self, obj):
        from usuario_localizacion.serializers import UsuarioLocalizacionSerializer
        
        usuario_localizacion = obj.localizaciones.filter(localizacion__isPrimary=True).select_related('localizacion').first()
        
        if usuario_localizacion:
            return UsuarioLocalizacionSerializer(usuario_localizacion).data
        
        return None
    def get_esta_abierta(self, obj) -> bool:
        empresa = obj.empresas_administradas.first()
        if not empresa:
            return False
        return empresa.esta_abierta()

    
class SocialLoginSerializer(serializers.Serializer):
    firebase_token = serializers.CharField(required=True)
    email          = serializers.EmailField(required=True)
    nombre         = serializers.CharField(required=False, allow_blank=True, default='')
    foto_url       = serializers.URLField(required=False, allow_blank=True, default='')

class RequestPasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()

class ConfirmPasswordResetSerializer(serializers.Serializer):
    token        = serializers.UUIDField()
    new_password = serializers.CharField(min_length=8)