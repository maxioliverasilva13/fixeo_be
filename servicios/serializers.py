from rest_framework import serializers
from .models import Servicio, ServicioImagen
from profesion.serializers import ProfesionSerializer
from empresas.currency_validation import validar_divisa_empresa
from empresas.delivery_utils import aplicar_limites_modalidad, modalidad_desde_usuario


class ServicioImagenSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServicioImagen
        fields = ['id', 'url', 'orden']
        read_only_fields = ['id']


class ServicioSerializer(serializers.ModelSerializer):
    profesion_detalle = ProfesionSerializer(source='profesion', read_only=True)
    usa_precio_rango = serializers.BooleanField(read_only=True)

    class Meta:
        model = Servicio
        fields = ['id', 'usuario', 'profesion', 'profesion_detalle', 'nombre', 'precio', 'precio_min', 'precio_max',
                  'usa_precio_rango', 'divisa', 'tiempo', 'notas', 'foto',
                  'acepta_domicilio', 'acepta_retiro', 'created_at', 'updated_at']
        read_only_fields = ['id', 'usuario', 'created_at', 'updated_at']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['imagenes'] = ServicioImagenSerializer(
            instance.imagenes.filter(is_deleted=False).order_by('orden', 'id'),
            many=True,
        ).data
        return data


def _sync_servicio_imagenes(servicio, imagenes_data):
    if imagenes_data is None:
        return
    keep_ids = []
    for i, raw in enumerate(imagenes_data):
        img_id = raw.get('id')
        url = (raw.get('url') or '').strip()
        if not url:
            continue
        orden = raw.get('orden', i)
        if img_id:
            img = servicio.imagenes.filter(id=img_id).first()
            if img:
                img.url = url
                img.orden = orden
                img.is_deleted = False
                img.deleted_at = None
                img.save()
                keep_ids.append(img.id)
                continue
        img = ServicioImagen.objects.create(
            servicio=servicio,
            url=url,
            orden=orden,
        )
        keep_ids.append(img.id)
    servicio.imagenes.exclude(id__in=keep_ids).filter(is_deleted=False).update(is_deleted=True)


class ServicioCreateSerializer(serializers.ModelSerializer):
    # En modo rango el precio de referencia lo deriva el backend (precio = precio_min),
    # así que el cliente puede omitirlo.
    precio = serializers.DecimalField(max_digits=10, decimal_places=2, required=False)
    imagenes = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True,
        write_only=True,
    )

    class Meta:
        model = Servicio
        fields = ['profesion', 'nombre', 'precio', 'precio_min', 'precio_max', 'divisa', 'tiempo', 'notas', 'foto',
                  'acepta_domicilio', 'acepta_retiro', 'imagenes']

    def create(self, validated_data):
        imagenes = validated_data.pop('imagenes', None)
        servicio = Servicio.objects.create(**validated_data)
        _sync_servicio_imagenes(servicio, imagenes)
        return servicio

    def update(self, instance, validated_data):
        imagenes = validated_data.pop('imagenes', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        _sync_servicio_imagenes(instance, imagenes)
        return instance

    def validate_precio(self, value):
        if value <= 0:
            raise serializers.ValidationError("El precio debe ser mayor a 0")
        return value
    
    def validate_tiempo(self, value):
        if value <= 0:
            raise serializers.ValidationError("El tiempo debe ser mayor a 0")
        return value

    def _validar_precio(self, attrs):
        """Un servicio tiene precio fijo O un rango de precios, nunca los dos ni ninguno.

        En modo rango `precio` queda como valor de referencia (se sincera a
        `precio_min`) para no romper listados, búsquedas ni sumas de trabajos.
        """
        precio_min = attrs.get('precio_min', getattr(self.instance, 'precio_min', None))
        precio_max = attrs.get('precio_max', getattr(self.instance, 'precio_max', None))
        precio = attrs.get('precio', getattr(self.instance, 'precio', None))

        if (precio_min is None) != (precio_max is None):
            raise serializers.ValidationError({
                'precio_min': 'Completá el precio mínimo y el máximo, o ninguno de los dos.',
            })

        if precio_min is not None:
            if precio_min <= 0:
                raise serializers.ValidationError({'precio_min': 'El precio mínimo debe ser mayor a 0'})
            if precio_max < precio_min:
                raise serializers.ValidationError({'precio_max': 'El precio máximo no puede ser menor al mínimo'})
            attrs['precio'] = precio_min
            return

        if precio is None:
            raise serializers.ValidationError({'precio': 'Indicá un precio fijo o un rango de precios'})

    def validate(self, attrs):
        self._validar_precio(attrs)

        request = self.context.get('request')
        empresa = self.context.get('empresa')
        servicio_owner = self.context.get('servicio_owner')
        usuario = servicio_owner or (getattr(request, 'user', None) if request else None)
        if not usuario:
            return attrs
        if empresa is None:
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
