from rest_framework import serializers
from .models import Servicio
from profesion.serializers import ProfesionSerializer
from empresas.currency_validation import validar_divisa_empresa
from empresas.delivery_utils import aplicar_limites_modalidad, modalidad_desde_usuario


class ServicioSerializer(serializers.ModelSerializer):
    profesion_detalle = ProfesionSerializer(source='profesion', read_only=True)
    
    class Meta:
        model = Servicio
        fields = ['id', 'usuario', 'profesion', 'profesion_detalle', 'nombre', 'precio', 'divisa', 'tiempo', 'notas', 'foto',
                  'acepta_domicilio', 'acepta_retiro', 'created_at', 'updated_at']
        read_only_fields = ['id', 'usuario', 'created_at', 'updated_at']


class ServicioCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Servicio
        fields = ['profesion', 'nombre', 'precio', 'divisa', 'tiempo', 'notas', 'foto', 'acepta_domicilio', 'acepta_retiro']
    
    def validate_precio(self, value):
        if value <= 0:
            raise serializers.ValidationError("El precio debe ser mayor a 0")
        return value
    
    def validate_tiempo(self, value):
        if value <= 0:
            raise serializers.ValidationError("El tiempo debe ser mayor a 0")
        return value

    def validate(self, attrs):
        request = self.context.get('request')
        usuario = getattr(request, 'user', None) if request else None
        if not usuario:
            return attrs
        empresa = usuario.empresas_administradas.first()
        divisa = attrs.get('divisa')
        if divisa is None and self.instance:
            divisa = self.instance.divisa
        if empresa and divisa:
            validar_divisa_empresa(empresa, divisa)

        default_domicilio, default_retiro = modalidad_desde_usuario(usuario)
        acepta_domicilio = attrs.get('acepta_domicilio', default_domicilio if self.instance is None else self.instance.acepta_domicilio)
        acepta_retiro = attrs.get('acepta_retiro', default_retiro if self.instance is None else self.instance.acepta_retiro)
        acepta_domicilio, acepta_retiro = aplicar_limites_modalidad(usuario, acepta_domicilio, acepta_retiro)
        attrs['acepta_domicilio'] = acepta_domicilio
        attrs['acepta_retiro'] = acepta_retiro
        return attrs
