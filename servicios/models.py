from django.db import models
from fixeo_project.models import BaseModel
from usuario.models import Usuario
from profesion.models import Profesion


class Servicio(BaseModel):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='servicios')
    profesion = models.ForeignKey(Profesion, on_delete=models.CASCADE, related_name='servicios')
    nombre = models.CharField(max_length=200, default='')
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    divisa = models.CharField(max_length=10, default='ARS')
    tiempo = models.IntegerField(help_text='Tiempo estimado en minutos')
    notas = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'usuario_servicios'
        verbose_name = 'Servicio'
        verbose_name_plural = 'Servicios'
        unique_together = ['usuario', 'profesion', 'nombre']

    def __str__(self):
        return f"{self.usuario} - {self.profesion} - {self.nombre}"
