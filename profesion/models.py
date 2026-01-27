from django.db import models
from fixeo_project.models import BaseModel


class Profesion(BaseModel):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    logo_svg_url = models.URLField(max_length=500, blank=True, null=True)

    class Meta:
        db_table = 'profesion'
        verbose_name = 'Profesión'
        verbose_name_plural = 'Profesiones'

    def __str__(self):
        return self.nombre
