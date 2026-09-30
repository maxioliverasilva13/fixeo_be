"""
Notifica a los admins (is_staff) cuando un usuario propone una profesión nueva
desde el registro. Sólo se dispara para profesiones que nacen `pendiente`
(ver profesion.views.ProfesionViewSet.proponer) — las creadas desde el admin
o por seed nacen `aprobada` y no generan esta notificación.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profesion


def notificar_admins_profesion_pendiente(profesion: Profesion):
    from usuario.models import Usuario
    from notificaciones.tasks import notificar_usuario

    staff_ids = list(
        Usuario.objects.filter(is_staff=True, is_active=True, is_deleted=False)
        .values_list('id', flat=True)
    )
    if not staff_ids:
        return

    titulo = 'Nueva profesión propuesta'
    mensaje = f'Un usuario propuso la profesión "{profesion.nombre}" desde el registro. Revisala para aprobarla o rechazarla.'
    data = {
        'deep_link': '/profesiones',
        'entity_id': profesion.id,
        'tipo': 'profesion_pendiente',
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
            try:
                notificar_usuario(uid, titulo, mensaje, data)
            except Exception:
                pass


@receiver(post_save, sender=Profesion)
def on_profesion_creada(sender, instance, created, **kwargs):
    if not created or kwargs.get('raw'):
        return
    if instance.estado != Profesion.ESTADO_PENDIENTE:
        return
    notificar_admins_profesion_pendiente(instance)
