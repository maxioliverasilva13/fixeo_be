from django.db import models
from usuario.models import Usuario
from fixeo_project.models import BaseModel
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector
from enums.enums import CURRENCY_CHOICES

class Empresa(BaseModel):
    PAIS_CHOICES = [
        ('AR', 'Argentina'),
        ('BO', 'Bolivia'),
        ('BR', 'Brasil'),
        ('CL', 'Chile'),
        ('CO', 'Colombia'),
        ('CR', 'Costa Rica'),
        ('CU', 'Cuba'),
        ('DO', 'República Dominicana'),
        ('EC', 'Ecuador'),
        ('GT', 'Guatemala'),
        ('HN', 'Honduras'),
        ('MX', 'México'),
        ('NI', 'Nicaragua'),
        ('PA', 'Panamá'),
        ('PE', 'Perú'),
        ('PR', 'Puerto Rico'),
        ('PY', 'Paraguay'),
        ('SV', 'El Salvador'),
        ('UY', 'Uruguay'),
        ('VE', 'Venezuela'),
    ]

    # Mapeo de nombres completos de país (Mapbox/Nominatim) a código ISO
    COUNTRY_NAME_TO_CODE = {
        'argentina': 'AR', 'bolivia': 'BO', 'brasil': 'BR', 'brazil': 'BR',
        'chile': 'CL', 'colombia': 'CO', 'costa rica': 'CR', 'cuba': 'CU',
        'república dominicana': 'DO', 'republica dominicana': 'DO', 'dominican republic': 'DO',
        'ecuador': 'EC', 'el salvador': 'SV', 'guatemala': 'GT', 'honduras': 'HN',
        'mexico': 'MX', 'méxico': 'MX', 'nicaragua': 'NI', 'panama': 'PA', 'panamá': 'PA',
        'peru': 'PE', 'perú': 'PE', 'paraguay': 'PY', 'puerto rico': 'PR',
        'uruguay': 'UY', 'venezuela': 'VE',
    }

    nombre = models.CharField(max_length=200)
    ubicacion = models.CharField(max_length=255)
    descripcion = models.TextField()
    latitud = models.DecimalField(max_digits=10, decimal_places=7)
    longitud = models.DecimalField(max_digits=10, decimal_places=7)
    pais = models.CharField(max_length=5, choices=PAIS_CHOICES, default='UY')
    unipersonal = models.BooleanField(default=False)
    vende_productos = models.BooleanField(default=False)
    vende_servicios = models.BooleanField(default=False)
    acepta_efectivo = models.BooleanField(default=True)
    acepta_tarjeta = models.BooleanField(default=True)
    is_mercadopago_vinculado = models.BooleanField(default=False)
    mp_access_token = models.TextField(blank=True, default='')
    mp_refresh_token = models.TextField(blank=True, default='')
    mp_user_id = models.CharField(max_length=100, blank=True, default='')
    mp_email = models.EmailField(blank=True, default='')
    localizacion = models.ForeignKey('localizacion.Localizacion', on_delete=models.SET_NULL, null=True, related_name='empresas')
    admin_id = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='empresas_administradas')
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        null=True,
        blank=True,
        default='UY'
    )
    class Meta:
        db_table = 'empresa'
        verbose_name = 'Empresa'
        verbose_name_plural = 'Empresas'

    def __str__(self):
        return self.nombre


class Horarios(BaseModel):
    dia_semana = models.CharField(max_length=20)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    enabled = models.BooleanField(default=True)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='horarios')

    class Meta:
        db_table = 'horarios'
        verbose_name = 'Horario'
        verbose_name_plural = 'Horarios'

    def __str__(self):
        return f"{self.empresa} - {self.dia_semana}"


class CategoriaProducto(BaseModel):
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, default='')
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='categorias_productos')

    class Meta:
        db_table = 'categoria_producto'
        verbose_name = 'Categoría de Producto'
        verbose_name_plural = 'Categorías de Productos'
        unique_together = ['nombre', 'empresa']

    def __str__(self):
        return f"{self.empresa.nombre} - {self.nombre}"


class Producto(BaseModel):
    nombre = models.CharField(max_length=200, db_index=True)
    descripcion = models.TextField(blank=True, default='')
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    codigo = models.CharField(max_length=100, blank=True, default='')
    agotado = models.BooleanField(default=False)
    foto = models.URLField(max_length=500, blank=True, default='')
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='productos')
    categoria = models.ForeignKey(CategoriaProducto, on_delete=models.SET_NULL, null=True, blank=True, related_name='productos')

    class Meta:
        db_table = 'producto'
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['agotado', '-created_at']
        indexes = [
            GinIndex(
                fields=["nombre"],
                name="producto_nombre_trgm",
                opclasses=["gin_trgm_ops"]
            ),
            models.Index(fields=['nombre']),
            models.Index(fields=['empresa', 'nombre']),
        ]

    def __str__(self):
        return f"{self.empresa.nombre} - {self.nombre}"

