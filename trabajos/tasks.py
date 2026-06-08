import logging
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from notificaciones.tasks import notificar_usuario
from trabajos.models import Calificacion, Trabajo

logger = logging.getLogger(__name__)


def _recordatorio_calificacion_countdown_seconds() -> int:
    minutos = getattr(settings, 'TRABAJO_CALIFICACION_RECORDATORIO_MINUTOS', 5)
    return max(0, int(minutos)) * 60


def _auto_finalizar_grace_delta() -> timedelta:
    minutos = getattr(settings, 'TRABAJO_CALIFICACION_RECORDATORIO_MINUTOS', 5)
    return timedelta(minutes=max(0, int(minutos)))


def programar_recordatorio_calificacion(trabajo_id: int) -> str | None:
    """Encola el push de calificación con el delay configurado."""
    result = enviar_recordatorio_calificacion_trabajo.apply_async(
        args=[trabajo_id],
        countdown=_recordatorio_calificacion_countdown_seconds(),
    )
    return result.id


@shared_task(name='trabajos.enviar_recordatorio_calificacion_trabajo')
def enviar_recordatorio_calificacion_trabajo(trabajo_id: int):
    logger.info
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
        if not trabajo.usuario_id or not trabajo.profesional_id:
            continue
        programar_recordatorio_calificacion(trabajo.id)
        recordatorios_programados += 1

    logger.info(
        "Trabajos auto-finalizados: %s | IDs: %s | Recordatorios en %s min: %s",
        count,
        ids_finalizados,
        getattr(settings, 'TRABAJO_CALIFICACION_RECORDATORIO_MINUTOS', 5),
        recordatorios_programados,
    )

    return {
        'finalizados': count,
        'ids': ids_finalizados,
        'limite': limite.isoformat(),
        'recordatorios_programados': recordatorios_programados,
    }
