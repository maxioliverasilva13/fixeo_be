from rest_framework import serializers
from servicios.serializers import ServicioSerializer
from .models import Empresa, CategoriaProducto, Producto, ProductoDia, ProductoVariante
from localizacion.serializers import LocalizacionSerializer
from .currency_validation import validar_divisa_empresa
from .delivery_utils import aplicar_limites_modalidad, modalidad_desde_usuario


class EmpresaSerializer(serializers.ModelSerializer):
    descripcion = serializers.CharField(required=False, allow_blank=True)
    trabajo_domicilio = serializers.BooleanField(source='admin_id.trabajo_domicilio', read_only=True)
    trabajo_local = serializers.BooleanField(source='admin_id.trabajo_local', read_only=True)
    efectivo_disponible = serializers.SerializerMethodField()
    metodos_pago_disponibles = serializers.SerializerMethodField()
    moneda_local = serializers.CharField(read_only=True)
    subscripcion = serializers.SerializerMethodField()
    admin_id = serializers.IntegerField(source='admin_id.id', read_only=True)
    tiene_landing_activa = serializers.SerializerMethodField()

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
            'vende_menu_diario',
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
            'admin_id',
            'created_at',
            'updated_at',
            'currency',
            'compartir_ubicacion_mapa',
            'subdomain',
            'landing_titulo',
            'landing_slogan',
            'landing_descripcion',
            'landing_foto_url',
            'tiene_landing_page',
            'tiene_landing_activa',
        ]
        read_only_fields = ['currency', 'moneda_local', 'tiene_landing_activa']

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

    def get_tiene_landing_activa(self, obj):
        from .utils import empresa_tiene_landing_activa
        return empresa_tiene_landing_activa(obj)

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
                'duracion_dias': subscripcion.plan_id.duracion.days if subscripcion.plan_id.duracion else 0,
                'cantidad_jobs': subscripcion.plan_id.cantidad_jobs,
            },
            'expiracion': subscripcion.expiracion.isoformat() if subscripcion.expiracion else None,
            'jobs_restantes': subscripcion.jobs_restantes,
            'cancelada': subscripcion.cancelada,
            'source': subscripcion.source,
            'status': subscripcion.status,
            'created_at': subscripcion.created_at.isoformat() if subscripcion.created_at else None,
        }


class CategoriaProductoSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = CategoriaProducto
        fields = ['id', 'nombre', 'descripcion', 'empresa', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class ProductoVarianteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductoVariante
        fields = ['id', 'nombre', 'precio_extra', 'activo', 'orden']
        read_only_fields = ['id']


class ProductoSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.CharField(source='categoria.nombre', read_only=True)
    # write_only: en el modelo `variantes` es RelatedManager; no se puede
    # serializar con ListField. La lectura va en to_representation.
    dias_semana = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=7),
        required=False,
        allow_empty=True,
        write_only=True,
    )
    variantes = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True,
        write_only=True,
    )

    class Meta:
        model = Producto
        fields = [
            'id', 'nombre', 'descripcion', 'precio', 'divisa', 'codigo', 'agotado', 'foto',
            'empresa', 'categoria', 'categoria_nombre', 'acepta_domicilio', 'acepta_retiro',
            'es_menu_diario', 'dias_semana', 'variantes',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        dias = list(instance.dias_menu.filter(is_deleted=False).order_by('dia_semana'))
        data['dias_semana'] = [d.dia_semana for d in dias if d.activo]
        data['dias_detalle'] = [
            {'dia_semana': d.dia_semana, 'activo': d.activo} for d in dias
        ]
        data['variantes'] = ProductoVarianteSerializer(
            instance.variantes.filter(is_deleted=False, activo=True).order_by('orden', 'id'),
            many=True,
        ).data
        # Contexto de listado filtrado por día (worker toggle)
        dia_ctx = self.context.get('dia_semana')
        if dia_ctx is not None:
            match = next((d for d in dias if d.dia_semana == int(dia_ctx)), None)
            data['activo_en_dia'] = match.activo if match else None
        return data

    def validate_dias_semana(self, value):
        if value is None:
            return []
        return sorted({int(d) for d in value if 1 <= int(d) <= 7})

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

        es_menu = attrs.get(
            'es_menu_diario',
            getattr(self.instance, 'es_menu_diario', False) if self.instance else False,
        )
        if es_menu and self.instance is None:
            dias = attrs.get('dias_semana')
            if dias is not None and len(dias) == 0:
                raise serializers.ValidationError({
                    'dias_semana': 'Un plato de menú diario necesita al menos un día.',
                })
        return attrs

    def _sync_dias(self, producto, dias_semana):
        if dias_semana is None:
            return
        actuales = set(
            producto.dias_menu.filter(is_deleted=False).values_list('dia_semana', flat=True)
        )
        nuevos = set(dias_semana)
        for dia in actuales - nuevos:
            producto.dias_menu.filter(dia_semana=dia, is_deleted=False).update(is_deleted=True)
        for dia in nuevos - actuales:
            existing = producto.dias_menu.filter(dia_semana=dia).first()
            if existing:
                if existing.is_deleted:
                    existing.is_deleted = False
                    existing.deleted_at = None
                    existing.activo = True
                    existing.save(update_fields=['is_deleted', 'deleted_at', 'activo', 'updated_at'])
            else:
                ProductoDia.objects.create(producto=producto, dia_semana=dia, activo=True)

    def _sync_variantes(self, producto, variantes_data):
        if variantes_data is None:
            return
        keep_ids = []
        for i, raw in enumerate(variantes_data):
            vid = raw.get('id')
            nombre = (raw.get('nombre') or '').strip()
            if not nombre:
                continue
            precio_extra = raw.get('precio_extra', 0)
            activo = raw.get('activo', True)
            orden = raw.get('orden', i)
            if vid:
                var = producto.variantes.filter(id=vid).first()
                if var:
                    var.nombre = nombre
                    var.precio_extra = precio_extra
                    var.activo = activo
                    var.orden = orden
                    var.is_deleted = False
                    var.deleted_at = None
                    var.save()
                    keep_ids.append(var.id)
                    continue
            var = ProductoVariante.objects.create(
                producto=producto,
                nombre=nombre,
                precio_extra=precio_extra,
                activo=activo,
                orden=orden,
            )
            keep_ids.append(var.id)
        producto.variantes.exclude(id__in=keep_ids).filter(is_deleted=False).update(is_deleted=True)

    def create(self, validated_data):
        dias = validated_data.pop('dias_semana', None)
        variantes = validated_data.pop('variantes', None)
        producto = Producto.objects.create(**validated_data)
        if producto.es_menu_diario:
            self._sync_dias(producto, dias if dias is not None else [])
            self._sync_variantes(producto, variantes or [])
        return producto

    def update(self, instance, validated_data):
        dias = validated_data.pop('dias_semana', None)
        variantes = validated_data.pop('variantes', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if instance.es_menu_diario:
            if dias is not None:
                self._sync_dias(instance, dias)
            if variantes is not None:
                self._sync_variantes(instance, variantes)
        return instance
