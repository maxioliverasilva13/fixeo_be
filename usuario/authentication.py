from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication


def get_token_inactivity_delta() -> timedelta:
    days = getattr(settings, 'JWT_INACTIVITY_DAYS', 30)
    return timedelta(days=max(1, int(days)))


def touch_token_activity(user) -> None:
    """Marca actividad de sesión (extiende la ventana de inactividad de 30 días)."""
    now = timezone.now()
    type(user).objects.filter(pk=user.pk).update(token_ultima_actividad=now)
    user.token_ultima_actividad = now


class SlidingJWTAuthentication(JWTAuthentication):
    """
    JWT con ventana deslizante: si el usuario no usa la app por JWT_INACTIVITY_DAYS,
    la sesión expira aunque el token siga siendo válido criptográficamente.
    Cada request autenticado renueva la fecha de última actividad.
    """

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None

        user, validated_token = result
        now = timezone.now()
        last_activity = getattr(user, 'token_ultima_actividad', None)

        if last_activity and (now - last_activity) > get_token_inactivity_delta():
            raise AuthenticationFailed(
                'Sesión expirada por inactividad. Volvé a iniciar sesión.',
                code='session_inactive',
            )

        touch_token_activity(user)
        return user, validated_token
