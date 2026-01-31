from django.db import models
from usuario.models import Usuario
from fixeo_project.models import BaseModel


class Empresa(BaseModel):
    nombre = models.CharField(max_length=200)
    ubicacion = models.CharField(max_length=255)
    descripcion = models.TextField()
    latitud = models.DecimalField(max_digits=10, decimal_places=7)
    longitud = models.DecimalField(max_digits=10, decimal_places=7)
    unipersonal = models.BooleanField(default=False)
    localizacion = models.ForeignKey('localizacion.Localizacion', on_delete=models.SET_NULL, null=True, related_name='empresas')
    admin_id = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='empresas_administradas')

    class Meta:
        db_table = 'empresa'
        verbose_name = 'Empresa'
        verbose_name_plural = 'Empresas'

    def __str__(self):
        return self.nombre


class Horarios(BaseModel):
    dia_semana = models.CharField(max_length=20)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    enabled = models.BooleanField(default=True)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='horarios')

    class Meta:
        db_table = 'horarios'
        verbose_name = 'Horario'
        verbose_name_plural = 'Horarios'

    def __str__(self):
        return f"{self.empresa} - {self.dia_semana}"


