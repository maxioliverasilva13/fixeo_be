from django.db import models
from disponibilidad.models import Disponibilidad
from localizacion.models import Localizacion
from usuario.models import Usuario
from servicios.models import Servicio
from fixeo_project.models import BaseModel
from profesion.models import Profesion


class Trabajo(BaseModel):
    STATUS_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('pendiente_urgente', 'Pendiente Urgente'),
        ('aceptado', 'Aceptado'),
        ('finalizado', 'Finalizado'),
        ('cancelado', 'Cancelado'), 
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendiente')
    esUrgente = models.BooleanField(default=False)
    fecha_inicio = models.DateTimeField(null=True, blank=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)
    descripcion = models.TextField()
    precio_final = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    comentario_cliente = models.TextField(blank=True, null=True)
    cancelado_cliente = models.BooleanField(default=False)
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='trabajos_solicitados')
    profesional = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True, related_name='trabajos_asignados')
    disponibilidad = models.ForeignKey(Disponibilidad, on_delete=models.SET_NULL, null=True, blank=True, related_name='trabajos')
    localizacion = models.ForeignKey(Localizacion, on_delete=models.SET_NULL, null=True, blank=True, related_name='trabajos')
    es_domicilio_profesional = models.BooleanField(default=False)
    profesion_urgente = models.ForeignKey(Profesion, on_delete=models.SET_NULL, null=True, blank=True, related_name='trabajos_urgentes')
    radio_busqueda_km = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text='Radio de búsqueda para trabajos urgentes')
    
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


class OfertaTrabajo(BaseModel):
    STATUS_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('aceptada', 'Aceptada'),
        ('rechazada', 'Rechazada'),
    ]
    
    trabajo = models.ForeignKey(Trabajo, on_delete=models.CASCADE, related_name='ofertas')
    profesional = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='ofertas_realizadas')
    precio_ofertado = models.DecimalField(max_digits=10, decimal_places=2)
    tiempo_estimado = models.IntegerField(help_text='Tiempo estimado en minutos')
    mensaje = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendiente')
    
    class Meta:
        db_table = 'oferta_trabajo'
        verbose_name = 'Oferta de Trabajo'
        verbose_name_plural = 'Ofertas de Trabajo'
        unique_together = ['trabajo', 'profesional']
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Oferta de {self.profesional} para {self.trabajo.id} - ${self.precio_ofertado}"