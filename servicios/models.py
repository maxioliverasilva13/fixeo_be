from django.db import models
from fixeo_project.models import BaseModel
from usuario.models import Usuario
from profesion.models import Profesion


class Servicio(BaseModel):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='servicios')
    profesion = models.ForeignKey(Profesion, on_delete=models.CASCADE, related_name='servicios')
    nombre = models.CharField(max_length=200, default='')
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    # Precio a convenir: un servicio tiene precio fijo O un rango, nunca los dos.
    # Si `precio_min` y `precio_max` están seteados, el servicio se muestra como
    # rango y `precio` queda como valor de referencia (se sincera a `precio_min`).
    precio_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    precio_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    divisa = models.CharField(max_length=10, default='ARS')
    tiempo = models.IntegerField(help_text='Tiempo estimado en minutos')
    notas = models.TextField(blank=True, default='')
    foto = models.URLField(max_length=500, blank=True, default='')
    acepta_domicilio = models.BooleanField(default=True)
    acepta_retiro = models.BooleanField(default=True)

    class Meta:
        db_table = 'usuario_servicios'
        verbose_name = 'Servicio'
        verbose_name_plural = 'Servicios'
        unique_together = ['usuario', 'profesion', 'nombre']

    def __str__(self):
        return f"{self.usuario} - {self.profesion} - {self.nombre}"

    @property
    def usa_precio_rango(self) -> bool:
        """True si el servicio se ofrece con precio a convenir (rango)."""
        return self.precio_min is not None and self.precio_max is not None


class ServicioImagen(BaseModel):
    """Foto adicional de un servicio. La de menor `orden` es la principal."""
    servicio = models.ForeignKey(Servicio, on_delete=models.CASCADE, related_name='imagenes')
    url = models.URLField(max_length=500)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = 'servicio_imagen'
        verbose_name = 'Imagen de servicio'
        verbose_name_plural = 'Imágenes de servicio'
        ordering = ['orden', 'id']
        indexes = [
            models.Index(fields=['servicio', 'orden'], name='idx_servicio_imagen_orden'),
        ]

    def __str__(self):
        return f"{self.servicio_id} - imagen {self.orden}"
