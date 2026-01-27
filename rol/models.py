from django.db import models
from fixeo_project.models import BaseModel


class Rol(BaseModel):
    TIPO_CHOICES = [
        ('admin', 'Admin'),
        ('usuario', 'Usuario'),
        ('profesional', 'Profesional'),
    ]
    nombre = models.CharField(max_length=50, choices=TIPO_CHOICES, unique=True)

    class Meta:
        db_table = 'rol'
        verbose_name = 'Rol'
        verbose_name_plural = 'Roles'

    def __str__(self):
        return self.nombre
