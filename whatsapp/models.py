from django.conf import settings
from django.db import models


class ConversacionWhatsApp(models.Model):
    """Estado de la conversación de un número de WhatsApp con el agente Fixeo.

    Guarda a qué usuario está asociado el número (si se conoce/creó), la
    ubicación estimada del cliente, en qué flujo/estado va la conversación y el
    historial reciente para dar contexto al LLM entre mensajes.
    """

    FLUJO_CLIENTE = 'cliente'
    FLUJO_ONBOARDING_PROFESIONAL = 'onboarding_profesional'
    FLUJO_CHOICES = [
        (FLUJO_CLIENTE, 'Cliente'),
        (FLUJO_ONBOARDING_PROFESIONAL, 'Onboarding profesional'),
    ]

    ESTADO_IDLE = 'idle'
    ESTADO_ESPERANDO_UBICACION = 'esperando_ubicacion'
    ESTADO_RECOLECTANDO_DATOS_PROF = 'recolectando_datos_prof'
    ESTADO_CONFIRMANDO_RESERVA = 'confirmando_reserva'
    ESTADO_ARMANDO_PEDIDO = 'armando_pedido'
    ESTADO_CONFIRMANDO_PEDIDO = 'confirmando_pedido'
    ESTADO_CHOICES = [
        (ESTADO_IDLE, 'Inactivo'),
        (ESTADO_ESPERANDO_UBICACION, 'Esperando ubicación'),
        (ESTADO_RECOLECTANDO_DATOS_PROF, 'Recolectando datos profesional'),
        (ESTADO_CONFIRMANDO_RESERVA, 'Confirmando reserva'),
        (ESTADO_ARMANDO_PEDIDO, 'Armando pedido'),
        (ESTADO_CONFIRMANDO_PEDIDO, 'Confirmando pedido'),
    ]

    wa_id = models.CharField(max_length=32, unique=True, db_index=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='conversaciones_whatsapp',
    )
    flujo = models.CharField(max_length=32, choices=FLUJO_CHOICES, default=FLUJO_CLIENTE)
    estado = models.CharField(max_length=32, choices=ESTADO_CHOICES, default=ESTADO_IDLE)

    ubicacion_lat = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    ubicacion_lon = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    ciudad = models.CharField(max_length=120, blank=True, default='')
    pais = models.CharField(max_length=80, blank=True, default='')

    # Datos parciales del flujo activo (slots de onboarding, borrador de reserva/pedido…).
    slots = models.JSONField(default=dict, blank=True)
    # Historial reciente de turnos [{'role': 'user'|'assistant', 'content': '...'}]
    historial = models.JSONField(default=list, blank=True)

    ultima_actividad = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-ultima_actividad']
        verbose_name = 'Conversación de WhatsApp'
        verbose_name_plural = 'Conversaciones de WhatsApp'

    def __str__(self):
        return f"{self.wa_id} ({self.flujo}/{self.estado})"

    @property
    def tiene_ubicacion(self) -> bool:
        return self.ubicacion_lat is not None and self.ubicacion_lon is not None


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
