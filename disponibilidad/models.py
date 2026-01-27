from django.db import models
from fixeo_project.models import BaseModel
from usuario.models import Usuario


class Disponibilidad(BaseModel):
    user_id = models.IntegerField()
    fecha_yyyy_mm_dd = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    tipo_disponible = models.CharField(max_length=50, blank=True, null=True)
    tipo_bloqueado = models.CharField(max_length=50, blank=True, null=True)
    origen_manual = models.BooleanField(default=False)
    origen_trabajo = models.BooleanField(default=False)
    origen_empresa = models.BooleanField(default=False)
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='disponibilidades')

    class Meta:
        db_table = 'disponibilidad'
        verbose_name = 'Disponibilidad'
        verbose_name_plural = 'Disponibilidades'

    def __str__(self):
        return f"{self.usuario} - {self.fecha_yyyy_mm_dd}"
