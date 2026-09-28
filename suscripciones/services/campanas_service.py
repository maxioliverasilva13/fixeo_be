"""Elegibilidad del plan gratis y resolución de la campaña de marketing vigente."""

from django.utils import timezone

from ..models import CampanaMarketing, Subscripcion


def campana_vigente():
    """La campaña activa más reciente que sigue vigente, o None."""
    for campana in CampanaMarketing.objects.filter(activa=True).order_by('-fecha_inicio'):
        if campana.esta_vigente():
            return campana
    return None


def usuario_elegible_plan_gratis(usuario) -> bool:
    """
    False si el usuario ya usó antes una suscripción otorgada por una campaña
    (de cualquier plan) y ya venció: no se le vuelve a ofrecer una promo gratis.
    """
    if usuario is None or not getattr(usuario, 'is_authenticated', True):
        return True
    return not Subscripcion.objects.filter(
        user_id=usuario,
        campana__isnull=False,
        expiracion__lte=timezone.now(),
    ).exists()
