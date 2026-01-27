from django.db import models
from usuario.models import Usuario
from empresas.models import Servicios
from fixeo_project.models import BaseModel


class Trabajo(BaseModel):
    categoria = models.CharField(max_length=100, blank=True, null=True)
    subcategoria_id = models.IntegerField(null=True, blank=True)
    trabajo_id = models.IntegerField(null=True, blank=True)
    status = models.CharField(max_length=50, blank=True, null=True)
    titulo = models.CharField(max_length=200)
    fecha_inicio = models.DateTimeField(null=True, blank=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)
    descripcion = models.TextField()
    precio_final = models.DecimalField(max_digits=10, decimal_places=2)
    comentario_cliente = models.TextField(blank=True, null=True)
    cancelado_cliente = models.BooleanField(default=False)
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='trabajos_solicitados')
    profesional = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='trabajos_asignados')
    servicio = models.ForeignKey(Servicios, on_delete=models.SET_NULL, null=True, blank=True, related_name='trabajos')

    class Meta:
        db_table = 'trabajo'
        verbose_name = 'Trabajo'
        verbose_name_plural = 'Trabajos'

    def __str__(self):
        return f"{self.titulo} - {self.status}"


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


class Estados(BaseModel):
    TIPO_CHOICES = [
        ('aceptado', 'Aceptado'),
        ('pendiente', 'Pendiente'),
        ('finalizado', 'Finalizado'),
    ]
    nombre = models.CharField(max_length=100, choices=TIPO_CHOICES, unique=True)
    finalizador = models.BooleanField(default=False)

    class Meta:
        db_table = 'estados'
        verbose_name = 'Estado'
        verbose_name_plural = 'Estados'

    def __str__(self):
        return self.nombre

