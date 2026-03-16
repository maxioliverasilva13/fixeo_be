from django.db import models
from fixeo_project.models import BaseModel
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector


class Profesion(BaseModel):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    logo_svg_url = models.URLField(max_length=500, blank=True, null=True)

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
