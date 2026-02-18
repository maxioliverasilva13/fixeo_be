from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import Usuario
from rol.serializers import RolSerializer
from django.db.models import Prefetch
from empresas.serializers import EmpresaSerializer

class UsuarioSortSerializer(serializers.ModelSerializer):
    rol_detalle = RolSerializer(source='rol', read_only=True)
    empresa = serializers.SerializerMethodField()
    localizacion_principal = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = ['id', 'correo', 'nombre', 'apellido', 'telefono', 'foto_url', 
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


class UsuarioSerializer(serializers.ModelSerializer):
    profesiones = serializers.SerializerMethodField()
    localizaciones = serializers.SerializerMethodField()
    servicios = serializers.SerializerMethodField()
    empresa = serializers.SerializerMethodField()
    rol_detalle = RolSerializer(source='rol', read_only=True)
    foto_map_url = serializers.SerializerMethodField()
    localizacion_principal = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = ['id', 'correo', 'nombre', 'apellido', 'telefono', 'foto_url', 'foto_map_url',
                  'trabajo_domicilio', 'trabajo_local', 'is_owner_empresa', 
                  'is_active', 'rango_mapa_km', 'created_at', 'updated_at', 'rol', 'rol_detalle', 'empresa',
                  'profesiones', 'localizaciones', 'localizacion_principal', 'servicios', 'is_configured', 'auto_aprobacion_trabajos']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_profesiones(self, obj):
        from profesion.serializers import ProfesionSerializer
        usuario_profesiones = obj.usuario_profesiones.all()
        return [ProfesionSerializer(up.profesion).data for up in usuario_profesiones]
    
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
    
    def get_foto_map_url(self, obj):
        if not obj.foto_url:
            return None

        return (
            obj.foto_url
            .replace(
                "/storage/v1/object/public/",
                "/storage/v1/render/image/public/"
            )
            + "?width=64&height=64&resize=cover"
        )
    
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


class UsuarioBasicInformationSerializer(serializers.ModelSerializer):
    localizacion = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = ['id', 'nombre', 'apellido', 'foto_url', 'telefono', 'localizacion']

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

    class Meta:
        model = Usuario
        fields = ['correo', 'password', 'password2', 'nombre', 'apellido', 'telefono', 'is_owner_empresa']

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Las contraseñas no coinciden."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        user = Usuario.objects.create_user(**validated_data)
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
    nombre = serializers.CharField(required=True, max_length=100)
    apellido = serializers.CharField(required=True, max_length=100)
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True, validators=[validate_password])
    es_empresa = serializers.BooleanField(required=True)
    trabajo_domicilio = serializers.BooleanField(required=True)
    trabajo_local = serializers.BooleanField(required=True)
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
        
        if not attrs.get('trabajo_domicilio') and not attrs.get('trabajo_local'):
            raise serializers.ValidationError("Debe seleccionar al menos un tipo de trabajo (domicilio o local).")
        
        return attrs

class FilterUsersMapaSerializer(serializers.Serializer):
    north = serializers.FloatField()
    south = serializers.FloatField()
    east = serializers.FloatField()
    west = serializers.FloatField()


class UpdateUsuarioSerializer(serializers.ModelSerializer):
    """
    Serializer para actualizar la información del usuario logueado
    """
    class Meta:
        model = Usuario
        fields = [
            'nombre', 
            'apellido', 
            'telefono', 
            'foto_url', 
            'trabajo_domicilio', 
            'trabajo_local',
            'rango_mapa_km',
            'auto_aprobacion_trabajos'
        ]
    
    def validate_rango_mapa_km(self, value):
        if value and value < 0.5:
            raise serializers.ValidationError("El rango mínimo es 0.5 km")
        if value and value > 50:
            raise serializers.ValidationError("El rango máximo es 150 km")
        return value
    
    def validate(self, attrs):
        trabajo_domicilio = attrs.get('trabajo_domicilio', self.instance.trabajo_domicilio if self.instance else None)
        trabajo_local = attrs.get('trabajo_local', self.instance.trabajo_local if self.instance else None)
        
        if trabajo_domicilio is not None and trabajo_local is not None:
            if not trabajo_domicilio and not trabajo_local:
                raise serializers.ValidationError(
                    "Debe tener al menos un tipo de trabajo activo (domicilio o local)."
                )
        
        return attrs


class UsuarioInMapaSerializer(serializers.ModelSerializer):
    profesiones = serializers.SerializerMethodField()
    localizacion = serializers.SerializerMethodField()


    class Meta:
        model = Usuario
        fields = ['id', 'nombre', 'apellido', 'foto_url', 'trabajo_domicilio', 
                  'trabajo_local', 'rango_mapa_km', 'profesiones', 'localizacion']
        read_only_fields = ['id', 'nombre', 'apellido', 'foto_url', 
                            'trabajo_domicilio', 'trabajo_local', 
                            'rango_mapa_km']
        
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

    

    
