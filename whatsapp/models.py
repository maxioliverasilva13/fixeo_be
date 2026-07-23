from django.conf import settings
from django.db import models


class WhatsAppMessage(models.Model):
    DIRECCION_ENTRANTE = 'entrante'
    DIRECCION_SALIENTE = 'saliente'
    DIRECCION_CHOICES = [
        (DIRECCION_ENTRANTE, 'Entrante'),
        (DIRECCION_SALIENTE, 'Saliente'),
    ]

    ESTADO_PENDIENTE = 'pendiente'
    ESTADO_ENVIADO = 'enviado'
    ESTADO_ENTREGADO = 'entregado'
    ESTADO_LEIDO = 'leido'
    ESTADO_FALLIDO = 'fallido'
    ESTADO_RECIBIDO = 'recibido'
    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE, 'Pendiente'),
        (ESTADO_ENVIADO, 'Enviado'),
        (ESTADO_ENTREGADO, 'Entregado'),
        (ESTADO_LEIDO, 'Leído'),
        (ESTADO_FALLIDO, 'Fallido'),
        (ESTADO_RECIBIDO, 'Recibido'),
    ]

    wa_id = models.CharField(max_length=32, db_index=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='mensajes_whatsapp',
    )
    direccion = models.CharField(max_length=10, choices=DIRECCION_CHOICES)
    tipo = models.CharField(max_length=20, default='text')
    wa_message_id = models.CharField(max_length=128, unique=True, null=True, blank=True)
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default=ESTADO_PENDIENTE)
    texto = models.TextField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Mensaje de WhatsApp'
        verbose_name_plural = 'Mensajes de WhatsApp'

    def __str__(self):
        return f"[{self.direccion}] {self.wa_id} ({self.estado})"
