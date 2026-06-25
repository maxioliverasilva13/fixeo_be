from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken

from .authentication import touch_token_activity
from .models import Usuario


class SlidingTokenRefreshView(TokenRefreshView):
    """Renueva tokens y extiende la ventana de inactividad al refrescar."""

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code != 200:
            return response

        refresh_raw = request.data.get('refresh')
        if not refresh_raw:
            return response

        try:
            token = RefreshToken(refresh_raw)
            user_id = token.get('user_id')
            if user_id:
                user = Usuario.objects.filter(pk=user_id, is_active=True).first()
                if user:
                    touch_token_activity(user)
        except Exception:
            pass

        return response
