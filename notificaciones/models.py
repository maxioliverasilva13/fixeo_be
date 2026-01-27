from django.db import models
from usuario.models import Usuario
from fixeo_project.models import BaseModel


class DeviceToken(BaseModel):
    device_name = models.CharField(max_length=100)
    enabled = models.BooleanField(default=True)
    device_token = models.CharField(max_length=255, unique=True)
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='device_tokens')

    class Meta:
        db_table = 'device_token'
        verbose_name = 'Device Token'
        verbose_name_plural = 'Device Tokens'

    def __str__(self):
        return f"{self.device_name} - {self.usuario}"


class Notificaciones(BaseModel):
    deep_link = models.CharField(max_length=255)
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField()
    entity_id = models.IntegerField()
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='notificaciones')

    class Meta:
        db_table = 'notificaciones'
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'

    def __str__(self):
        return self.titulo


class Notas(BaseModel):
    ESTADO_CHOICES = [
        ('aceptado', 'Aceptado'),
        ('pendiente', 'Pendiente'),
        ('finalizado', 'Finalizado'),
    ]

    roles = models.CharField(max_length=100, blank=True, null=True)
    admin = models.BooleanField(default=False)
    usuario = models.BooleanField(default=False)
    profesional = models.BooleanField(default=False)
    fecha_siempre_en_utc = models.DateTimeField()
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES)

    class Meta:
        db_table = 'notas'
        verbose_name = 'Nota'
        verbose_name_plural = 'Notas'

    def __str__(self):
        return f"Nota {self.estado} - {self.fecha_siempre_en_utc}"

