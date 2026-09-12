import logging
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from notificaciones.tasks import notificar_usuario
from trabajos.models import Calificacion, CalificacionDireccion, Trabajo
from whatsapp.models import WhatsAppMessage

logger = logging.getLogger(__name__)

_MESES_ES = [
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
]


def _recordatorio_calificacion_countdown_seconds() -> int:
    minutos = getattr(settings, 'RECORDATORIO_CALIFICAR_PROFESIONAL_TRABAJO_MINUTES', 1)
    return max(0, int(minutos)) * 60


def _nombre_completo(usuario, fallback: str) -> str:
    nombre = f"{usuario.nombre} {usuario.apellido}".strip()
    return nombre or fallback


def _servicio_trabajo_nombre(trabajo: Trabajo) -> str:
    """Nombre descriptivo del servicio del trabajo: servicios asociados, profesión urgente o descripción."""
    servicios = list(
        trabajo.trabajo_servicios
        .select_related('servicio')
        .values_list('servicio__nombre', flat=True)
    )
    servicios = [s for s in servicios if s]
    if servicios:
        return ', '.join(servicios)

    if trabajo.profesion_urgente_id and trabajo.profesion_urgente:
        return trabajo.profesion_urgente.nombre

    descripcion = (trabajo.descripcion or '').strip()
    if descripcion:
        return descripcion if len(descripcion) <= 60 else f"{descripcion[:57]}..."

    return 'tu servicio'


def _fecha_trabajo_formateada(trabajo: Trabajo) -> str:
    fecha = trabajo.fecha_fin or trabajo.fecha_inicio
    if not fecha:
        return ''
    fecha_local = timezone.localtime(fecha)
    mes = _MESES_ES[fecha_local.month - 1]
    return f"{fecha_local.day} de {mes} a las {fecha_local.strftime('%H:%M')}"


def _precio_trabajo_formateado(trabajo: Trabajo) -> str:
    if trabajo.precio_final is None:
        return ''
    moneda = trabajo.currency or ''
    return f"{trabajo.precio_final:.2f} {moneda}".strip()


def _detalle_trabajo_lineas(trabajo: Trabajo) -> str:
    """Líneas adicionales (fecha, precio) para el cuerpo del recordatorio, ya formateadas."""
    lineas = []
    fecha = _fecha_trabajo_formateada(trabajo)
    if fecha:
        lineas.append(f"📅 {fecha}")
    precio = _precio_trabajo_formateado(trabajo)
    if precio:
        lineas.append(f"💰 {precio}")
    return ('\n' + '\n'.join(lineas)) if lineas else ''


def ejecutar_post_finalizacion_trabajo(trabajo: Trabajo) -> dict:
    """
    Tras marcar un trabajo como finalizado: encola recordatorios de calificación
    (cliente + profesional) con RECORDATORIO_CALIFICAR_PROFESIONAL_TRABAJO_MINUTES.
    """
    if not trabajo.usuario_id or not trabajo.profesional_id:
        return {'recordatorios': None}

    return {'recordatorios': programar_recordatorio_calificacion(trabajo.id)}


def programar_recordatorio_calificacion(trabajo_id: int) -> dict:
    """Encola push de calificación para cliente y profesional con el delay configurado."""
    countdown = _recordatorio_calificacion_countdown_seconds()
    client_result = enviar_recordatorio_calificacion_trabajo.apply_async(
        args=[trabajo_id],
        countdown=countdown,
    )
    pro_result = enviar_recordatorio_calificacion_profesional.apply_async(
        args=[trabajo_id],
        countdown=countdown,
    )
    return {
        'client_task_id': client_result.id,
        'professional_task_id': pro_result.id,
    }


def _auto_finalizar_grace_delta() -> timedelta:
    minutos = getattr(settings, 'FINALIZACION_TRABAJO_DESPUES_DE_MINUTES', 1)
    return timedelta(minutes=max(0, int(minutos)))


@shared_task(name='trabajos.enviar_recordatorio_calificacion_trabajo')
def enviar_recordatorio_calificacion_trabajo(trabajo_id: int):
    trabajo = (
        Trabajo.objects
        .filter(id=trabajo_id, status='finalizado')
        .select_related('usuario', 'profesional', 'profesion_urgente')
        .prefetch_related('trabajo_servicios__servicio')
        .first()
    )
    if not trabajo:
        logger.info("Recordatorio calificación omitido: trabajo %s no finalizado", trabajo_id)
        return {'skipped': True, 'reason': 'not_finalizado', 'trabajo_id': trabajo_id}

    if not trabajo.usuario_id or not trabajo.profesional_id:
        return {'skipped': True, 'reason': 'missing_users', 'trabajo_id': trabajo_id}

    ya_calificado = Calificacion.objects.filter(
        trabajo_id=trabajo_id,
        user_cal_sender_id=trabajo.usuario_id,
        user_cal_recibe_id=trabajo.profesional_id,
        direccion=CalificacionDireccion.CLIENTE_A_PROFESIONAL,
    ).exists()
    if ya_calificado:
        logger.info("Recordatorio calificación omitido: trabajo %s ya calificado", trabajo_id)
        return {'skipped': True, 'reason': 'already_rated', 'trabajo_id': trabajo_id}

    profesional_nombre = _nombre_completo(trabajo.profesional, 'el profesional')
    servicio_nombre = _servicio_trabajo_nombre(trabajo)
    detalle = _detalle_trabajo_lineas(trabajo)

    notificar_usuario.delay(
        usuario_id=trabajo.usuario_id,
        titulo=f"⭐ Calificá a {profesional_nombre}",
        mensaje=(
            f"Tu servicio de {servicio_nombre} con {profesional_nombre} "
            f"ya finalizó.{detalle}\n¡Contanos cómo te fue!"
        ),
        data={
            'deep_link': f'/historial?trabajoId={trabajo_id}&calificar=true',
            'entity_id': trabajo_id,
            'trabajo_id': str(trabajo_id),
            'profesional_id': str(trabajo.profesional_id),
            'profesional_nombre': profesional_nombre,
            'servicio_nombre': servicio_nombre,
            'tipo': 'calificacion_pendiente',
        },
    )

    logger.info("Recordatorio calificación encolado para trabajo %s → usuario %s", trabajo_id, trabajo.usuario_id)
    return {
        'success': True,
        'trabajo_id': trabajo_id,
        'usuario_id': trabajo.usuario_id,
    }


@shared_task(name='trabajos.enviar_recordatorio_calificacion_profesional')
def enviar_recordatorio_calificacion_profesional(trabajo_id: int):
    trabajo = (
        Trabajo.objects
        .filter(id=trabajo_id, status='finalizado')
        .select_related('usuario', 'profesional', 'profesion_urgente')
        .prefetch_related('trabajo_servicios__servicio')
        .first()
    )
    if not trabajo:
        logger.info(
            "Recordatorio calificación pro omitido: trabajo %s no finalizado",
            trabajo_id,
        )
        return {'skipped': True, 'reason': 'not_finalizado', 'trabajo_id': trabajo_id}

    if not trabajo.usuario_id or not trabajo.profesional_id:
        return {'skipped': True, 'reason': 'missing_users', 'trabajo_id': trabajo_id}

    ya_calificado = Calificacion.objects.filter(
        trabajo_id=trabajo_id,
        user_cal_sender_id=trabajo.profesional_id,
        user_cal_recibe_id=trabajo.usuario_id,
        direccion=CalificacionDireccion.PROFESIONAL_A_CLIENTE,
    ).exists()
    if ya_calificado:
        logger.info(
            "Recordatorio calificación pro omitido: trabajo %s ya calificado por profesional",
            trabajo_id,
        )
        return {'skipped': True, 'reason': 'already_rated', 'trabajo_id': trabajo_id}

    cliente_nombre = _nombre_completo(trabajo.usuario, 'el cliente')
    servicio_nombre = _servicio_trabajo_nombre(trabajo)
    detalle = _detalle_trabajo_lineas(trabajo)

    notificar_usuario.delay(
        usuario_id=trabajo.profesional_id,
        titulo=f"⭐ Calificá a {cliente_nombre}",
        mensaje=(
            f"El servicio de {servicio_nombre} con {cliente_nombre} "
            f"ya finalizó.{detalle}\nCalificalo para completarlo."
        ),
        data={
            'deep_link': f'/historial?trabajoId={trabajo_id}&calificar=true',
            'entity_id': trabajo_id,
            'trabajo_id': str(trabajo_id),
            'cliente_id': str(trabajo.usuario_id),
            'cliente_nombre': cliente_nombre,
            'servicio_nombre': servicio_nombre,
            'tipo': 'calificacion_pendiente_profesional',
        },
    )

    logger.info(
        "Recordatorio calificación pro encolado para trabajo %s → profesional %s",
        trabajo_id,
        trabajo.profesional_id,
    )
    return {
        'success': True,
        'trabajo_id': trabajo_id,
        'profesional_id': trabajo.profesional_id,
    }


# ---------------------------------------------------------------------------
# Recordatorios de reserva al cliente (12 h y 1 h antes) — vía template WhatsApp
# ---------------------------------------------------------------------------
def _telefono_cliente_wa(trabajo: Trabajo):
    """Teléfono del cliente en formato WhatsApp: el del invitado si la reserva es
    de un invitado por WhatsApp, si no el del usuario. Devuelve None si no hay."""
    from whatsapp.services import normalizar_numero_whatsapp

    crudo = trabajo.phoneNumberInvitedUser or (
        trabajo.usuario.telefono if trabajo.usuario_id and trabajo.usuario else ''
    )
    crudo = (crudo or '').strip()
    return normalizar_numero_whatsapp(crudo) if crudo else None


@shared_task(name='trabajos.enviar_recordatorios_reservas')
def enviar_recordatorios_reservas():
    """Barrido periódico (beat): encola recordatorios de reservas confirmadas que
    cruzan el umbral de 12 h o 1 h antes de empezar. Idempotente por los campos
    recordatorio_*_enviado_at (el envío marca el campo)."""
    ahora = timezone.now()
    t12 = ahora + timedelta(hours=12)
    t1 = ahora + timedelta(hours=1)

    ids_12 = list(
        Trabajo.objects.filter(
            status='aceptado',
            fecha_inicio__isnull=False,
            fecha_inicio__gt=t1,
            fecha_inicio__lte=t12,
            recordatorio_12h_enviado_at__isnull=True,
        ).values_list('id', flat=True)
    )
    ids_1 = list(
        Trabajo.objects.filter(
            status='aceptado',
            fecha_inicio__isnull=False,
            fecha_inicio__gt=ahora,
            fecha_inicio__lte=t1,
            recordatorio_1h_enviado_at__isnull=True,
        ).values_list('id', flat=True)
    )

    for tid in ids_12:
        enviar_recordatorio_reserva_task.delay(tid, '12h')
    for tid in ids_1:
        enviar_recordatorio_reserva_task.delay(tid, '1h')

    logger.info("Recordatorios reservas encolados: 12h=%s | 1h=%s", ids_12, ids_1)
    return {'encolados_12h': ids_12, 'encolados_1h': ids_1}


@shared_task(name='trabajos.enviar_recordatorio_reserva_task')
def enviar_recordatorio_reserva_task(trabajo_id: int, tramo: str):
    """Envía el template de recordatorio al cliente y marca el tramo como enviado.
    Si el envío falla (p. ej. template aún no aprobado), NO marca el campo, así el
    beat lo reintenta en la próxima corrida."""
    from whatsapp import services

    campo = 'recordatorio_12h_enviado_at' if tramo == '12h' else 'recordatorio_1h_enviado_at'
    trabajo = (
        Trabajo.objects
        .filter(id=trabajo_id, status='aceptado')
        .select_related('usuario', 'profesional', 'profesion_urgente')
        .prefetch_related('trabajo_servicios__servicio')
        .first()
    )
    if not trabajo:
        return {'skipped': True, 'reason': 'not_found_or_status', 'trabajo_id': trabajo_id}
    if getattr(trabajo, campo):
        return {'skipped': True, 'reason': 'already_sent', 'trabajo_id': trabajo_id, 'tramo': tramo}

    telefono = _telefono_cliente_wa(trabajo)
    if not telefono:
        logger.info("Recordatorio %s omitido: trabajo %s sin teléfono de cliente", tramo, trabajo_id)
        return {'skipped': True, 'reason': 'no_phone', 'trabajo_id': trabajo_id}

    cliente_nombre = _nombre_completo(trabajo.usuario, 'cliente') if trabajo.usuario_id else 'cliente'
    servicio_nombre = _servicio_trabajo_nombre(trabajo)
    profesional_nombre = (
        _nombre_completo(trabajo.profesional, 'el profesional') if trabajo.profesional_id else 'el profesional'
    )
    fecha = _fecha_trabajo_formateada(trabajo) or 'la fecha acordada'
    cuando = '12 horas' if tramo == '12h' else '1 hora'

    componentes = [{
        'type': 'body',
        'parameters': [
            {'type': 'text', 'text': cliente_nombre},
            {'type': 'text', 'text': servicio_nombre},
            {'type': 'text', 'text': profesional_nombre},
            {'type': 'text', 'text': fecha},
            {'type': 'text', 'text': cuando},
        ],
    }]

    mensaje = services.enviar_template_mensaje(
        to=telefono,
        template_name=settings.WHATSAPP_TEMPLATE_RECORDATORIO,
        components=componentes,
        usuario=trabajo.usuario if trabajo.usuario_id else None,
    )

    if mensaje.estado == WhatsAppMessage.ESTADO_ENVIADO:
        setattr(trabajo, campo, timezone.now())
        trabajo.save(update_fields=[campo])
        logger.info("Recordatorio %s enviado para trabajo %s → %s", tramo, trabajo_id, telefono)
    else:
        logger.warning("Recordatorio %s FALLIDO para trabajo %s (se reintentará)", tramo, trabajo_id)

    return {'trabajo_id': trabajo_id, 'tramo': tramo, 'estado': mensaje.estado, 'telefono': telefono}


# ---------------------------------------------------------------------------
# Aviso al profesional al crearse una reserva — template con botón confirmar/rechazar
# ---------------------------------------------------------------------------
@shared_task(name='trabajos.enviar_template_confirmacion_trabajo_task')
def enviar_template_confirmacion_trabajo_task(trabajo_id: int):
    """Envía al profesional el template con el link (botón URL + token) para
    confirmar o rechazar el trabajo recién creado."""
    from whatsapp import services
    from trabajos.whatsapp_helpers import _direccion_trabajo

    trabajo = (
        Trabajo.objects
        .filter(id=trabajo_id)
        .select_related('usuario', 'profesional', 'profesion_urgente', 'localizacion')
        .prefetch_related('trabajo_servicios__servicio')
        .first()
    )
    if not trabajo:
        return {'skipped': True, 'reason': 'not_found', 'trabajo_id': trabajo_id}
    if not trabajo.profesional_id or not trabajo.profesional:
        return {'skipped': True, 'reason': 'no_profesional', 'trabajo_id': trabajo_id}

    telefono_crudo = (trabajo.profesional.telefono or '').strip()
    if not telefono_crudo:
        logger.info("Confirmación omitida: profesional %s sin teléfono", trabajo.profesional_id)
        return {'skipped': True, 'reason': 'no_phone', 'trabajo_id': trabajo_id}
    telefono = services.normalizar_numero_whatsapp(telefono_crudo)

    cliente_nombre = _nombre_completo(trabajo.usuario, 'un cliente') if trabajo.usuario_id else 'un cliente'
    servicio_nombre = _servicio_trabajo_nombre(trabajo)
    fecha = _fecha_trabajo_formateada(trabajo) or 'la fecha acordada'
    direccion = _direccion_trabajo(trabajo) or 'Sin dirección especificada'

    componentes = [
        {
            'type': 'body',
            'parameters': [
                {'type': 'text', 'text': cliente_nombre},
                {'type': 'text', 'text': servicio_nombre},
                {'type': 'text', 'text': fecha},
                {'type': 'text', 'text': direccion},
            ],
        },
        {
            'type': 'button',
            'sub_type': 'url',
            'index': '0',
            'parameters': [
                {'type': 'text', 'text': str(trabajo.token_confirmacion)},
            ],
        },
    ]

    mensaje = services.enviar_template_mensaje(
        to=telefono,
        template_name=settings.WHATSAPP_TEMPLATE_CONFIRMACION_TRABAJO,
        components=componentes,
        usuario=trabajo.profesional,
    )
    logger.info(
        "Template confirmación trabajo %s → profesional %s: estado=%s",
        trabajo_id, trabajo.profesional_id, mensaje.estado,
    )
    return {'trabajo_id': trabajo_id, 'estado': mensaje.estado, 'telefono': telefono}


@shared_task(name='trabajos.finalizar_trabajos_vencidos')
def finalizar_trabajos_vencidos():
    ahora = timezone.now()
    limite = ahora - _auto_finalizar_grace_delta()

    trabajos_qs = Trabajo.objects.filter(
        status__in=['pendiente', 'pendiente_urgente', 'aceptado'],
        fecha_fin__isnull=False,
        fecha_fin__lte=limite,
    ).select_related('usuario', 'profesional')\
     .prefetch_related('profesional__empresas_administradas')

    trabajos = list(trabajos_qs)

    if not trabajos:
        logger.info("No hay trabajos vencidos para finalizar (límite %s)", limite.isoformat())
        return {
            'finalizados': 0,
            'ids': [],
            'limite': limite.isoformat(),
            'recordatorios_programados': 0,
        }

    ids_finalizados = [t.id for t in trabajos]
    count = trabajos_qs.update(status='finalizado')

    try:
        from pagos.services import liberar_pagos_entidad
        for trabajo in trabajos:
            if trabajo.metodo_pago in ('mercadopago', 'tarjeta'):
                liberados = liberar_pagos_entidad('trabajo', trabajo.id)
                if liberados > 0:
                    logger.info("Liberados %d pagos para trabajo %s (auto-finalizado)", liberados, trabajo.id)
    except Exception:
        logger.exception("Error liberando pagos en finalización automática")

    recordatorios_programados = 0
    for trabajo in trabajos:
        trabajo.status = 'finalizado'
        ejecutar_post_finalizacion_trabajo(trabajo)
        if trabajo.usuario_id and trabajo.profesional_id:
            recordatorios_programados += 1

    logger.info(
        'Trabajos auto-finalizados: %s | IDs: %s | Recordatorios en %s min: %s',
        count,
        ids_finalizados,
        getattr(settings, 'RECORDATORIO_CALIFICAR_PROFESIONAL_TRABAJO_MINUTES', 1),
        recordatorios_programados,
    )

    return {
        'finalizados': count,
        'ids': ids_finalizados,
        'limite': limite.isoformat(),
        'recordatorios_programados': recordatorios_programados,
    }
