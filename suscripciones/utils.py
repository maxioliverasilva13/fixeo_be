def get_subscripcion_activa(usuario):
    """
    Devuelve la Subscripcion activa más reciente del usuario (cancelada=False
    y no vencida), o None si no tiene ninguna.
    """
    if not usuario:
        return None

    from django.utils import timezone
    from suscripciones.models import Subscripcion

    return (
        Subscripcion.objects
        .filter(
            user_id=usuario,
            cancelada=False,
            expiracion__gt=timezone.now(),
        )
        .select_related('plan_id')
        .order_by('-created_at')
        .first()
    )


def tiene_subscripcion_activa(usuario) -> bool:
    """True si el usuario tiene alguna suscripción activa (de cualquier plan)."""
    return get_subscripcion_activa(usuario) is not None


def usuario_tiene_plan_pago(usuario) -> bool:
    """
    True si el usuario (profesional) tiene una suscripción activa a un plan
    que no es el gratuito (precio > 0). Se usa para gatear funcionalidades
    premium como el envío de recordatorios por WhatsApp.
    """
    sub = get_subscripcion_activa(usuario)
    return bool(sub and sub.plan_id.precio > 0)
