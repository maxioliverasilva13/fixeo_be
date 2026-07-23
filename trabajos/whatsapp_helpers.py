from django.utils import timezone

MODALIDAD_TRABAJO_TEXTOS = {
    True: 'En el local del profesional',
    False: 'A domicilio',
}


def _detalle_servicios_trabajo(trabajo):
    """Ej: 'Corte de cabello, Barba' (o la profesión/descripción si es un trabajo urgente sin servicios)"""
    servicios = list(trabajo.trabajo_servicios.select_related('servicio').all())
    if servicios:
        return ', '.join(ts.servicio.nombre for ts in servicios)
    if trabajo.profesion_urgente_id:
        return trabajo.profesion_urgente.nombre
    return trabajo.descripcion[:120] if trabajo.descripcion else ''


def _total_formateado_trabajo(trabajo):
    if trabajo.precio_final is None:
        return 'A coordinar'
    moneda = f" {trabajo.currency}" if trabajo.currency else ''
    return f"${trabajo.precio_final}{moneda}"


def _direccion_trabajo(trabajo):
    """
    Dirección relevante según la modalidad: si es en el local del
    profesional, la del profesional; si es a domicilio, la del usuario.
    trabajo.localizacion ya queda resuelto a la dirección correcta al crear
    el trabajo.
    """
    loc = trabajo.localizacion
    if not loc:
        return ''
    direccion = loc.address or loc.ubicacion
    if loc.city:
        direccion = f"{direccion}, {loc.city}" if direccion else loc.city
    if not direccion:
        return ''
    etiqueta = 'Dirección del profesional' if trabajo.es_domicilio_profesional else 'Dirección de la visita'
    return f"{etiqueta}: {direccion}"


def mensaje_whatsapp_trabajo(trabajo, encabezado, motivo=None):
    """
    Arma un mensaje de WhatsApp con el detalle del trabajo/reserva:
    servicio/s, total, modalidad, dirección, fecha/hora, notas y motivo
    (si aplica). El encabezado ya debe traer resaltado con *...* lo
    importante (con quién es el trabajo, nuevo estado).
    """
    lineas = [encabezado]

    detalle = _detalle_servicios_trabajo(trabajo)
    if detalle:
        lineas.append(f"  Servicio/s: {detalle}")

    lineas.append(f"  Total: *{_total_formateado_trabajo(trabajo)}*")
    lineas.append(f"  Modalidad: {MODALIDAD_TRABAJO_TEXTOS.get(trabajo.es_domicilio_profesional, '')}")

    direccion = _direccion_trabajo(trabajo)
    if direccion:
        lineas.append(f"  {direccion}")

    if trabajo.fecha_inicio:
        fecha_local = timezone.localtime(trabajo.fecha_inicio)
        lineas.append(f"  Fecha: *{fecha_local.strftime('%d/%m/%Y')}*")
        lineas.append(f"  Hora: *{fecha_local.strftime('%H:%M')}*")

    if trabajo.descripcion:
        lineas.append(f"  Notas: {trabajo.descripcion}")

    if motivo:
        lineas.append(f"  Motivo: *{motivo}*")

    return '\n'.join(lineas)
