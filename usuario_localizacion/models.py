from django.db import models
from fixeo_project.models import BaseModel
from usuario.models import Usuario


class UsuarioLocalizacion(BaseModel):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='localizaciones')
    localizacion = models.ForeignKey('localizacion.Localizacion', on_delete=models.CASCADE, related_name='usuarios')
    es_principal = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'usuario_localizacion'
        verbose_name = 'Usuario Localización'
        verbose_name_plural = 'Usuario Localizaciones'
        unique_together = ['usuario', 'localizacion']
    
    def __str__(self):
        principal = " (Principal)" if self.es_principal else ""
        return f"{self.usuario} - {self.localizacion}{principal}"
    
    def save(self, *args, **kwargs):
        if self.es_principal:
            UsuarioLocalizacion.objects.filter(
                usuario=self.usuario,
                es_principal=True
            ).exclude(id=self.id).update(es_principal=False)
        super().save(*args, **kwargs)
