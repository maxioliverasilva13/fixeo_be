from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import Usuario
from rol.serializers import RolSerializer
from empresas.serializers import EmpresaSerializer

class UsuarioSerializer(serializers.ModelSerializer):
    profesiones = serializers.SerializerMethodField()
    disponibilidades = serializers.SerializerMethodField()
    localizaciones = serializers.SerializerMethodField()
    servicios = serializers.SerializerMethodField()  # <--- Nuevo campo
    empresa = serializers.SerializerMethodField()  # 👈 NUEVO
    rol_detalle = RolSerializer(source='rol', read_only=True)

    class Meta:
        model = Usuario
        fields = ['id', 'correo', 'nombre', 'apellido', 'telefono', 'foto_url', 
                  'trabajo_domicilio', 'trabajo_local', 'is_owner_empresa', 
                  'is_active', 'rango_mapa_km', 'created_at', 'updated_at', 'rol', 'rol_detalle', 'empresa',
                  'profesiones', 'localizaciones', 'disponibilidades', 'servicios', 'is_configured']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_profesiones(self, obj):
        from profesion.serializers import ProfesionSerializer
        usuario_profesiones = obj.usuario_profesiones.all()
        return [ProfesionSerializer(up.profesion).data for up in usuario_profesiones]
    
    def get_localizaciones(self, obj):
        from usuario_localizacion.serializers import UsuarioLocalizacionSerializer
        usuario_localizaciones = obj.localizaciones.select_related('localizacion').all()
        return UsuarioLocalizacionSerializer(usuario_localizaciones, many=True).data
    
    def get_disponibilidades(self, obj):
        from disponibilidad.serializers import DisponibilidadSerializer
        return DisponibilidadSerializer(obj.disponibilidades.all(), many=True).data

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

    

    
