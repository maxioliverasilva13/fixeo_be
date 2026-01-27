from django.db import models
from usuario.models import Usuario
from fixeo_project.models import BaseModel


class Chat(BaseModel):
    received_id = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='chats_recibidos')
    sender_id = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='chats_enviados')

    class Meta:
        db_table = 'chat'
        verbose_name = 'Chat'
        verbose_name_plural = 'Chats'

    def __str__(self):
        return f"Chat {self.sender_id} -> {self.received_id}"


class Mensajes(BaseModel):
    mensaje_id = models.AutoField(primary_key=True)
    texto = models.TextField()
    sender_id = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='mensajes_enviados')
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='mensajes')

    class Meta:
        db_table = 'mensajes'
        verbose_name = 'Mensaje'
        verbose_name_plural = 'Mensajes'

    def __str__(self):
        return f"Mensaje {self.mensaje_id} - Chat {self.chat}"


class Recurso(BaseModel):
    url = models.URLField(max_length=500)
    mensaje = models.ForeignKey(Mensajes, on_delete=models.CASCADE, related_name='recursos')

    class Meta:
        db_table = 'recurso'
        verbose_name = 'Recurso'
        verbose_name_plural = 'Recursos'

    def __str__(self):
        return f"Recurso {self.url}"

