from rest_framework import serializers
from servicios.serializers import ServicioSerializer
from .models import Empresa, CategoriaProducto, Producto
from localizacion.serializers import LocalizacionSerializer
from .currency_validation import validar_divisa_empresa
from .delivery_utils import aplicar_limites_modalidad, modalidad_desde_usuario


class EmpresaSerializer(serializers.ModelSerializer):
    trabajo_domicilio = serializers.BooleanField(source='admin_id.trabajo_domicilio', read_only=True)
    trabajo_local = serializers.BooleanField(source='admin_id.trabajo_local', read_only=True)
    efectivo_disponible = serializers.SerializerMethodField()
    metodos_pago_disponibles = serializers.SerializerMethodField()
    moneda_local = serializers.CharField(read_only=True)
    subscripcion = serializers.SerializerMethodField()

    class Meta:
        model = Empresa
        fields = [
            'id',
            'nombre',
            'ubicacion',
            'descripcion',
            'latitud',
            'longitud',
            'pais',
            'moneda_local',
            'unipersonal',
            'vende_productos',
            'vende_servicios',
            'acepta_efectivo',
            'acepta_tarjeta',
            'is_mercadopago_vinculado',
            'mp_user_id',
            'mp_email',
            'efectivo_disponible',
            'metodos_pago_disponibles',
            'trabajo_domicilio',
            'trabajo_local',
            'subscripcion',
            'created_at',
            'updated_at',
            'currency'
        ]
        read_only_fields = ['currency', 'moneda_local']

    def _get_efectivo_jobs_restantes(self, obj):
        """Devuelve (subscripcion, jobs_restantes_efectivo) o (None, 0). Cachea por empresa."""
        cache_key = '_efectivo_cache'
        if not hasattr(self, cache_key):
            setattr(self, cache_key, {})
        cache = getattr(self, cache_key)
        if obj.id in cache:
            return cache[obj.id]

        from suscripciones.models import Subscripcion
        from trabajos.models import Trabajo
        from django.utils import timezone
        from datetime import timedelta

        subscripcion = (
            Subscripcion.objects
            .filter(user_id=obj.admin_id, cancelada=False, expiracion__gt=timezone.now())
            .select_related('plan_id')
            .order_by('-created_at')
            .first()
        )
        if not subscripcion:
            cache[obj.id] = (None, 0)
            return None, 0

        inicio_periodo = subscripcion.expiracion - timedelta(days=30)
        usados = Trabajo.objects.filter(
            profesional=obj.admin_id,
            metodo_pago='efectivo',
            created_at__gte=inicio_periodo,
            is_deleted=False,
        ).exclude(status='cancelado').count()

        result = (subscripcion, max(0, subscripcion.plan_id.cantidad_jobs - usados))
        cache[obj.id] = result
        return result

    def get_efectivo_disponible(self, obj):
        """
        acepta_efectivo=True solo funciona si el admin tiene suscripción activa
        y le quedan trabajos en efectivo disponibles.
        """
        if not obj.acepta_efectivo:
            return False
        _, jobs_restantes = self._get_efectivo_jobs_restantes(obj)
        return jobs_restantes > 0

    def get_metodos_pago_disponibles(self, obj):
        """Lista de métodos de pago que la empresa realmente puede usar."""
        metodos = []
        if obj.acepta_tarjeta and obj.is_mercadopago_vinculado:
            metodos.append('mercadopago')
        if obj.acepta_efectivo:
            _, jobs_restantes = self._get_efectivo_jobs_restantes(obj)
            if jobs_restantes > 0:
                metodos.append('efectivo')
        return metodos

    def get_subscripcion(self, obj):
        """Devuelve la suscripción activa del admin de la empresa, si existe."""
        from suscripciones.models import Subscripcion
        from django.utils import timezone

        subscripcion = (
            Subscripcion.objects
            .filter(user_id=obj.admin_id, cancelada=False, expiracion__gt=timezone.now())
            .select_related('plan_id')
            .order_by('-created_at')
            .first()
        )
        if not subscripcion:
            return None

        return {
            'id': subscripcion.id,
            'plan': {
                'id': subscripcion.plan_id.id,
                'nombre': subscripcion.plan_id.nombre,
                'precio': str(subscripcion.plan_id.precio),
                'duracion_dias': subscripcion.plan_id.duracion_dias,
                'cantidad_jobs': subscripcion.plan_id.cantidad_jobs,
            },
            'expiracion': subscripcion.expiracion.isoformat() if subscripcion.expiracion else None,
            'jobs_extra': subscripcion.jobs_extra,
            'cancelada': subscripcion.cancelada,
            'fuente': subscripcion.fuente,
            'created_at': subscripcion.created_at.isoformat() if subscripcion.created_at else None,
        }


class CategoriaProductoSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = CategoriaProducto
        fields = ['id', 'nombre', 'descripcion', 'empresa', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductoSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.CharField(source='categoria.nombre', read_only=True)
    
    class Meta:
        model = Producto
        fields = ['id', 'nombre', 'descripcion', 'precio', 'divisa', 'codigo', 'agotado', 'foto', 
                  'empresa', 'categoria', 'categoria_nombre', 'acepta_domicilio', 'acepta_retiro',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate(self, attrs):
        empresa = attrs.get('empresa') or getattr(self.instance, 'empresa', None)
        divisa = attrs.get('divisa')
        if empresa and divisa is not None:
            validar_divisa_empresa(empresa, divisa)

        if empresa:
            admin = empresa.admin_id
            default_domicilio, default_retiro = modalidad_desde_usuario(admin)
            acepta_domicilio = attrs.get(
                'acepta_domicilio',
                default_domicilio if self.instance is None else self.instance.acepta_domicilio,
            )
            acepta_retiro = attrs.get(
                'acepta_retiro',
                default_retiro if self.instance is None else self.instance.acepta_retiro,
            )
            acepta_domicilio, acepta_retiro = aplicar_limites_modalidad(admin, acepta_domicilio, acepta_retiro)
            attrs['acepta_domicilio'] = acepta_domicilio
            attrs['acepta_retiro'] = acepta_retiro
        return attrs
