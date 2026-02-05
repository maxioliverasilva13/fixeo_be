from django.db import models
from disponibilidad.models import Disponibilidad
from localizacion.models import Localizacion
from usuario.models import Usuario
from servicios.models import Servicio
from fixeo_project.models import BaseModel


class Trabajo(BaseModel):
    STATUS_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('aceptado', 'Aceptado'),
        ('finalizado', 'Finalizado'),
        ('cancelado', 'Cancelado'), 
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendiente')
    esUrgente = models.BooleanField(default=False)
    status = models.CharField(max_length=50, blank=True, null=True)
    fecha_inicio = models.DateTimeField(null=True, blank=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)
    descripcion = models.TextField()
    precio_final = models.DecimalField(max_digits=10, decimal_places=2)
    comentario_cliente = models.TextField(blank=True, null=True)
    cancelado_cliente = models.BooleanField(default=False)
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='trabajos_solicitados')
    profesional = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='trabajos_asignados')
    disponibilidad = models.ForeignKey(Disponibilidad, on_delete=models.SET_NULL, null=True, blank=True, related_name='trabajos')
    localizacion = models.ForeignKey(Localizacion, on_delete=models.SET_NULL, null=True, blank=True, related_name='trabajos')
    es_domicilio_profesional = models.BooleanField(default=False)
    class Meta:
        db_table = 'trabajo'
        verbose_name = 'Trabajo'
        verbose_name_plural = 'Trabajos'

    def __str__(self):
        return f"{self.status}"


class Calificacion(BaseModel):
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    comentario = models.TextField(blank=True, null=True)
    user_cal_recibe = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='calificaciones_recibidas')
    user_cal_sender = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='calificaciones_enviadas')
    trabajo = models.ForeignKey(Trabajo, on_delete=models.CASCADE, related_name='calificaciones', null=True, blank=True)

    class Meta:
        db_table = 'calificacion'
        verbose_name = 'Calificación'
        verbose_name_plural = 'Calificaciones'

    def __str__(self):
        return f"Calificación {self.rating} - {self.trabajo}"


class TrabajoServicio(BaseModel):
    trabajo = models.ForeignKey(Trabajo, on_delete=models.CASCADE, related_name='trabajo_servicios')
    servicio = models.ForeignKey(Servicio, on_delete=models.CASCADE)
    precio = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    class Meta:
        db_table = 'trabajo_servicio'
        verbose_name = 'Trabajo Servicio'
        verbose_name_plural = 'Trabajo Servicios'

    def __str__(self):
        return f"{self.servicio.nombre}"