from django.db import models
from fixeo_project.models import BaseModel
from usuario.models import Usuario
from django.utils import timezone


class Tipo(models.TextChoices):
    DISPONIBLE = 'disponible', 'Disponible'
    OCUPADO = 'ocupado', 'Ocupado'
    BLOQUEADO = 'bloqueado', 'Bloqueado'
class Origen(models.TextChoices):
    MANUAL = 'manual', 'Manual'
    TRABAJO = 'trabajo', 'Trabajo'
    EMPRESA = 'empresa', 'Empresa'
    SISTEMA = 'sistema', 'Sistema'

class Disponibilidad(BaseModel):


    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name='disponibilidades'
    )

    fecha_inicio = models.DateTimeField(default=timezone.now)
    fecha_fin = models.DateTimeField(default=timezone.now)

    tipo = models.CharField(
        max_length=20,
        choices=Tipo.choices,
        default=Tipo.DISPONIBLE
    )

    origen = models.CharField(
        max_length=20,
        choices=Origen.choices,
        default=Origen.MANUAL
    )

    class Meta:
        db_table = 'disponibilidad'
        verbose_name = 'Disponibilidad'
        verbose_name_plural = 'Disponibilidades'
        indexes = [
            models.Index(fields=['usuario', 'fecha_inicio', 'fecha_fin']),
        ]

    def __str__(self):
        return f"{self.usuario} | {self.fecha_inicio} - {self.fecha_fin} ({self.tipo})"
