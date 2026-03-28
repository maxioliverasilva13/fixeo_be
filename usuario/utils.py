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