from django.db import models
from usuario.models import Usuario
from fixeo_project.models import BaseModel
from trabajos.models import Trabajo

class Chat(BaseModel):
    sender = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='chats_enviados')
    receiver = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='chats_recibidos')
    trabajo = models.ForeignKey('trabajos.Trabajo', on_delete=models.SET_NULL, null=True, blank=True, related_name='chats')
    ultimo_mensaje_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'chat'
        verbose_name = 'Chat'
        verbose_name_plural = 'Chats'
        ordering = ['-ultimo_mensaje_at']

    def __str__(self):
        return f"Chat entre {self.sender} y {self.receiver}"


class Mensajes(BaseModel):
    
    class TipoMensaje(models.TextChoices):
        TEXTO = 'texto', 'Texto'
        CALIFICACION = 'calificacion', 'Calificación'
        IMAGEN = 'imagen', 'Imagen'
        ARCHIVO = 'archivo', 'Archivo'

    mensaje_id = models.AutoField(primary_key=True)
    texto = models.TextField(blank=True)  
    tipo = models.CharField(
        max_length=20,
        choices=TipoMensaje.choices,
        default=TipoMensaje.TEXTO
    )
    sender = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='mensajes_enviados')
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='mensajes')
    trabajo = models.ForeignKey(                          
        'trabajos.Trabajo',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mensajes'
    )
    leido = models.BooleanField(default=False)
    metadata = models.JSONField(null=True, blank=True)


class Recurso(BaseModel):
    url = models.URLField(max_length=500)
    tipo = models.CharField(max_length=50, blank=True)
    nombre = models.CharField(max_length=255, blank=True)
    mensaje = models.ForeignKey(Mensajes, on_delete=models.CASCADE, related_name='recursos', null=True, blank=True)
    chat = models.ForeignKey(
        Chat,
        on_delete=models.CASCADE,
        related_name='recursos',
        null=True,
        blank=True
    )
    trabajo = models.ForeignKey(
        Trabajo,
        on_delete=models.CASCADE,
        related_name='recursos',
        null=True,
        blank=True
    )

    class Meta:
        db_table = 'recurso'
        verbose_name = 'Recurso'
        verbose_name_plural = 'Recursos'

    def __str__(self):
        return f"Recurso {self.nombre or self.url}"

