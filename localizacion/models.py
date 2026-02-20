from django.db import models
from fixeo_project.models import BaseModel


class Localizacion(BaseModel):
    ubicacion = models.CharField(max_length=255)
    latitud = models.DecimalField(max_digits=10, decimal_places=7)
    longitud = models.DecimalField(max_digits=10, decimal_places=7)
    address = models.TextField(blank=True, null=True)
    notas = models.TextField(blank=True, null=True)
    interior_door = models.CharField(max_length=50, blank=True, null=True)
    city = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    county = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    isPrimary = models.BooleanField(default=False)
    class Meta:
        db_table = 'localizacion'
        verbose_name = 'Localización'
        verbose_name_plural = 'Localizaciones'
        indexes = [
            models.Index(fields=['latitud'], name='idx_localizacion_latitud'),
            models.Index(fields=['longitud'], name='idx_localizacion_longitud'),
            models.Index(fields=['latitud', 'longitud'], name='idx_localizacion_geo'),
        ]

    def __str__(self):
        return f"{self.city}, {self.country}"
