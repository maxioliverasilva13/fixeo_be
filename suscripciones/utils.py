def usuario_tiene_plan_pago(usuario) -> bool:
    """
    True si el usuario (profesional) tiene una suscripción activa a un plan
    que no es el gratuito (precio > 0). Se usa para gatear funcionalidades
    premium como el envío de recordatorios por WhatsApp.
    """
    if not usuario:
        return False

    from django.utils import timezone
    from suscripciones.models import Subscripcion

    sub = (
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
    return bool(sub and sub.plan_id.precio > 0)
