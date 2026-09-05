"""
Promo de onboarding para las primeras empresas (landing page gratis).
Usado en registro (tiene_landing_page) y mensajes/emails de bienvenida.
"""
from .models import Empresa

WELCOME_WEB_URL = 'https://alavueltaapp.pro'
EMPRESAS_ACTIVAS_PROMO_THRESHOLD = 100


def count_empresas_activas() -> int:
    return Empresa.objects.filter(
        admin_id__is_active=True,
        admin_id__is_deleted=False,
    ).count()


def welcome_usa_promo_landing(empresas_activas: int | None = None) -> bool:
    """True mientras haya menos de EMPRESAS_ACTIVAS_PROMO_THRESHOLD empresas activas."""
    if empresas_activas is None:
        empresas_activas = count_empresas_activas()
    return empresas_activas < EMPRESAS_ACTIVAS_PROMO_THRESHOLD
