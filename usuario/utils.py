def foto_usuario_api(valor):
    """Para respuestas JSON: sin foto (None o vacío) -> string vacía."""
    return valor if valor else 'https://static.vecteezy.com/system/resources/thumbnails/019/879/186/small/user-icon-on-transparent-background-free-png.png'


def obtener_localizacion_usuario(usuario):
    rel = (
        usuario.localizaciones
        .select_related('localizacion')
        .order_by('-es_principal', 'created_at')
        .first()
    )

    return rel.localizacion if rel else None


def registrar_visita_perfil(profesional, request=None):
    """
    Registra que alguien (que no es el dueño) intentó ver el perfil de un
    profesional sin suscripción activa. `request` se usa solo para evitar
    loguear al propio dueño; si no hay usuario autenticado se registra igual
    (visitante anónimo).
    """
    if request is not None and request.user.is_authenticated and request.user.id == profesional.id:
        return

    from usuario.models import VisitaPerfil
    VisitaPerfil.objects.create(profesional=profesional)