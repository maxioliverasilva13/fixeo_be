from django.db import models
from usuario.models import Usuario
from fixeo_project.models import BaseModel


class Plan(BaseModel):
    nombre = models.CharField(max_length=200, default='Plan Básico')
    descripcion = models.TextField(blank=True, default='')
    precio = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cantidad_personas = models.IntegerField(default=1)
    duracion = models.DurationField()
    google_play_id = models.CharField(max_length=200, blank=True, null=True)
    appstore_id = models.CharField(max_length=200, blank=True, null=True)
    caracteristicas = models.JSONField(default=list)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = 'plan'
        verbose_name = 'Plan'
        verbose_name_plural = 'Planes'

    def __str__(self):
        return f"Plan {self.plan_id_stripe} - {self.usuario}"


class Subscripcion(BaseModel):
    expiracion = models.DateTimeField()
    plan_id = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name='subscripciones')
    user_id = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='subscripciones')
    cancelada = models.BooleanField(default=False)

    class Meta:
        db_table = 'subscripcion'
        verbose_name = 'Subscripción'
        verbose_name_plural = 'Subscripciones'

    def __str__(self):
        return f"Subscripción {self.user_id} - {self.plan_id}"

