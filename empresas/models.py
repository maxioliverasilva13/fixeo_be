from django.db import models
from usuario.models import Usuario
from fixeo_project.models import BaseModel


class Empresa(BaseModel):
    nombre = models.CharField(max_length=200)
    ubicacion = models.CharField(max_length=255)
    descripcion = models.TextField()
    latitud = models.DecimalField(max_digits=10, decimal_places=7)
    longitud = models.DecimalField(max_digits=10, decimal_places=7)
    unipersonal = models.BooleanField(default=False)
    vende_productos = models.BooleanField(default=False)
    vende_servicios = models.BooleanField(default=False)
    localizacion = models.ForeignKey('localizacion.Localizacion', on_delete=models.SET_NULL, null=True, related_name='empresas')
    admin_id = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='empresas_administradas')

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
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, default='')
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    codigo = models.CharField(max_length=100, blank=True, default='')
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='productos')
    categoria = models.ForeignKey(CategoriaProducto, on_delete=models.SET_NULL, null=True, blank=True, related_name='productos')
    foto = models.URLField(max_length=500, blank=True, default='')  # ← nuevo

    class Meta:
        db_table = 'producto'
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'

    def __str__(self):
        return f"{self.empresa.nombre} - {self.nombre}"

