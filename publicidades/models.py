from django.db import models
from fixeo_project.models import BaseModel


class Publicidad(BaseModel):
    TIPO_CHOICES = [
        ('contador', 'Contador'),
        ('texto', 'Texto'),
        ('imagen', 'Imagen'),
    ]

    DIRIGIDO_CHOICES = [
        ('usuario', 'Usuario'),
        ('profesional', 'Profesional'),
        ('ambos', 'Ambos'),
    ]

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    dirigido_a = models.CharField(max_length=20, choices=DIRIGIDO_CHOICES, default='ambos')
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    imagen_url = models.URLField(blank=True, null=True)
    fecha_expiracion = models.DateTimeField(blank=True, null=True)
    activa = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'publicidades'
        verbose_name = 'Publicidad'
        verbose_name_plural = 'Publicidades'
        ordering = ['orden', '-created_at']

    def __str__(self):
        return self.titulo
