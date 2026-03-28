def foto_usuario_api(valor):
    """Para respuestas JSON: sin foto (None o vacío) -> string vacía."""
    return valor if valor else ''


def obtener_localizacion_usuario(usuario):
    rel = (
        usuario.localizaciones
        .select_related('localizacion')
        .order_by('-es_principal', 'created_at')
        .first()
    )

    return rel.localizacion if rel else None