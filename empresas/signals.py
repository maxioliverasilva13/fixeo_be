"""
Notifica a todos los admins (is_staff) cuando se crea una empresa nueva.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from empresas.models import Empresa, ProductoImagen


@receiver(post_save, sender=Empresa)
def notificar_admins_empresa_nueva(sender, instance, created, **kwargs):
    if not created:
        return
    # Evitar notificar en seeds/bulk si el flag está activo
    if kwargs.get('raw'):
        return

    from usuario.models import Usuario
    from notificaciones.tasks import notificar_usuario

    staff_ids = list(
        Usuario.objects.filter(is_staff=True, is_active=True, is_deleted=False)
        .values_list('id', flat=True)
    )
    if not staff_ids:
        return

    titulo = 'Nueva empresa registrada'
    mensaje = f'Se registró la empresa "{instance.nombre}"'
    if instance.pais:
        mensaje += f' ({instance.pais})'
    data = {
        'deep_link': '/empresas',
        'entity_id': instance.id,
        'tipo': 'empresa_nueva',
    }

    for uid in staff_ids:
        try:
            notificar_usuario.delay(
                usuario_id=uid,
                titulo=titulo,
                mensaje=mensaje,
                data=data,
            )
        except Exception:
            # Fallback síncrono si Celery no está disponible
            try:
                notificar_usuario(uid, titulo, mensaje, data)
            except Exception:
                pass


def _sync_producto_foto(producto_id):
    """Mantiene `Producto.foto` como la URL de la imagen de menor `orden`."""
    from empresas.models import Producto

    primary = (
        ProductoImagen.objects.filter(producto_id=producto_id, is_deleted=False)
        .order_by('orden', 'id')
        .first()
    )
    Producto.objects.filter(pk=producto_id).update(foto=primary.url if primary else '')


@receiver(post_save, sender=ProductoImagen)
def on_producto_imagen_saved(sender, instance, **kwargs):
    if kwargs.get('raw'):
        return
    _sync_producto_foto(instance.producto_id)


@receiver(post_delete, sender=ProductoImagen)
def on_producto_imagen_deleted(sender, instance, **kwargs):
    _sync_producto_foto(instance.producto_id)
