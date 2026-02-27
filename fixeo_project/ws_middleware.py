from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from urllib.parse import parse_qs

@database_sync_to_async
def get_user_from_token(token_key):
    from django.contrib.auth.models import AnonymousUser
    from rest_framework_simplejwt.tokens import AccessToken
    from django.contrib.auth import get_user_model

    User = get_user_model()
    try:
        token = AccessToken(token_key)
        user_id = token['user_id']
        return User.objects.get(id=user_id)
    except Exception as e:
        print(f"[JWT MIDDLEWARE] Error: {e}")
        return AnonymousUser()

class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        from django.contrib.auth.models import AnonymousUser

        query_string = scope.get('query_string', b'').decode()
        params = parse_qs(query_string)
        token = params.get('token', [None])[0]

        print(f"[JWT MIDDLEWARE] token encontrado: {bool(token)}")

        scope['user'] = await get_user_from_token(token) if token else AnonymousUser()

        print(f"[JWT MIDDLEWARE] user: {scope['user']} authenticated: {scope['user'].is_authenticated}")

        return await super().__call__(scope, receive, send)