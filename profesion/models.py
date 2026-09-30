from django.db import models
from fixeo_project.models import BaseModel
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector


class Profesion(BaseModel):
    ESTADO_PENDIENTE = 'pendiente'
    ESTADO_APROBADA = 'aprobada'
    ESTADO_RECHAZADA = 'rechazada'
    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE, 'Pendiente'),
        (ESTADO_APROBADA, 'Aprobada'),
        (ESTADO_RECHAZADA, 'Rechazada'),
    ]

    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    logo_svg_url = models.URLField(max_length=500, blank=True, null=True)
    # Las profesiones cargadas por admin/seed nacen aprobadas. Sólo la propuesta
    # de un usuario durante el registro (ver profesion.views.proponer) nace
    # pendiente, y es lo único que dispara la notificación push al admin.
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default=ESTADO_APROBADA)

    class Meta:
        db_table = 'profesion'
        indexes = [
            GinIndex(
                fields=["nombre"],
                name="profesion_nombre_trgm",
                opclasses=["gin_trgm_ops"]
            )
        ]
        verbose_name = 'Profesión'
        verbose_name_plural = 'Profesiones'

    def __str__(self):
        return self.nombre
