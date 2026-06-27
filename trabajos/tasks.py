import logging
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from notificaciones.tasks import notificar_usuario
from trabajos.models import Calificacion, CalificacionDireccion, Trabajo

logger = logging.getLogger(__name__)


def _recordatorio_calificacion_countdown_seconds() -> int:
    minutos = getattr(settings, 'RECORDATORIO_CALIFICAR_PROFESIONAL_TRABAJO_MINUTES', 1)
    return max(0, int(minutos)) * 60


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
        .select_related('usuario', 'profesional')
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

    profesional_nombre = (
        f"{trabajo.profesional.nombre} {trabajo.profesional.apellido}".strip()
        or 'el profesional'
    )

    notificar_usuario.delay(
        usuario_id=trabajo.usuario_id,
        titulo=f"Califica a {profesional_nombre}",
        mensaje=f"Tu trabajo con {profesional_nombre} ha finalizado. ¡Califícalo ahora!",
        data={
            'deep_link': f'/historial?trabajoId={trabajo_id}&calificar=true',
            'entity_id': trabajo_id,
            'trabajo_id': str(trabajo_id),
            'profesional_id': str(trabajo.profesional_id),
            'profesional_nombre': profesional_nombre,
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
        .select_related('usuario', 'profesional')
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

    cliente_nombre = (
        f"{trabajo.usuario.nombre} {trabajo.usuario.apellido}".strip()
        or 'el cliente'
    )

    notificar_usuario.delay(
        usuario_id=trabajo.profesional_id,
        titulo=f"Califica a {cliente_nombre}",
        mensaje=f"Tu trabajo con {cliente_nombre} ha finalizado. ¡Califícalo ahora!",
        data={
            'deep_link': f'/historial?trabajoId={trabajo_id}&calificar=true',
            'entity_id': trabajo_id,
            'trabajo_id': str(trabajo_id),
            'cliente_id': str(trabajo.usuario_id),
            'cliente_nombre': cliente_nombre,
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
