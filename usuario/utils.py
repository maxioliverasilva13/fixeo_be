

def obtener_localizacion_usuario(usuario):
    rel = (
        usuario.localizaciones
        .select_related('localizacion')
        .order_by('-es_principal', 'created_at')
        .first()
    )

    return rel.localizacion if rel else None