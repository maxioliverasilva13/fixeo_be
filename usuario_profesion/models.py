from django.db import models
from fixeo_project.models import BaseModel
from usuario.models import Usuario
from profesion.models import Profesion


class UsuarioProfesion(BaseModel):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='usuario_profesiones')
    profesion = models.ForeignKey(Profesion, on_delete=models.CASCADE, related_name='profesion_usuarios')

    class Meta:
        db_table = 'usuario_profesion'
        verbose_name = 'Usuario Profesión'
        verbose_name_plural = 'Usuario Profesiones'
        unique_together = ['usuario', 'profesion']
        indexes = [
            models.Index(fields=['profesion', 'usuario'], name='idx_up_profesion_usuario'),
        ]

    def __str__(self):
        return f"{self.usuario} - {self.profesion}"
