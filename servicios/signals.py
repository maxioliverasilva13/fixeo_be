"""
Mantiene `Servicio.foto` sincronizado con la imagen principal (menor `orden`).
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from servicios.models import ServicioImagen


def _sync_servicio_foto(servicio_id):
    from servicios.models import Servicio

    primary = (
        ServicioImagen.objects.filter(servicio_id=servicio_id, is_deleted=False)
        .order_by('orden', 'id')
        .first()
    )
    Servicio.objects.filter(pk=servicio_id).update(foto=primary.url if primary else '')


@receiver(post_save, sender=ServicioImagen)
def on_servicio_imagen_saved(sender, instance, **kwargs):
    if kwargs.get('raw'):
        return
    _sync_servicio_foto(instance.servicio_id)


@receiver(post_delete, sender=ServicioImagen)
def on_servicio_imagen_deleted(sender, instance, **kwargs):
    _sync_servicio_foto(instance.servicio_id)
