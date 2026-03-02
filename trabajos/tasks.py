import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

from notificaciones.tasks import notificar_usuarios_multiple
from trabajos.models import Trabajo

logger = logging.getLogger(__name__)


@shared_task
def finalizar_trabajos_vencidos():
    ahora = timezone.now()
    limite = ahora - timedelta(days=1)
    
    trabajos_qs = Trabajo.objects.filter(
        status__in=['pendiente', 'pendiente_urgente', 'aceptado'],
        fecha_fin__isnull=False,
        fecha_fin__lte=limite,
    ).select_related('usuario', 'profesional')
    
    trabajos = list(trabajos_qs)
    
    if not trabajos:
        logger.info("No hay trabajos vencidos para finalizar")
        return {
            'finalizados': 0,
            'ids': [],
            'limite': limite.isoformat(),
            'notificaciones_enviadas': 0,
        }
    
    ids_finalizados = [t.id for t in trabajos]
    count = trabajos_qs.update(status='finalizado')
    
    notificaciones_enviadas = 0
    usuarios_notificados = set()
    
    for trabajo in trabajos:
        if not trabajo.usuario_id or not trabajo.profesional_id:
            continue
            
        usuario_id = trabajo.usuario_id
        profesional_id = trabajo.profesional_id
        trabajo_id = trabajo.id
        
        profesional_nombre = (
            f"{trabajo.profesional.nombre} {trabajo.profesional.apellido}".strip()
            or 'el profesional'
        )
        
        notificar_usuarios_multiple.delay(
            usuarios_ids=[usuario_id],
            titulo=f"Califica a {profesional_nombre}",
            mensaje=f"Tu trabajo con {profesional_nombre} ha finalizado. ¡Califícalo ahora!",
            data={
                'deep_link': f'fixeo://trabajos/{trabajo_id}/calificar?profesionalId={profesional_id}',
                'trabajo_id': str(trabajo_id),
                'profesional_id': str(profesional_id),
                'profesional_nombre': profesional_nombre,
                'tipo': 'calificacion_pendiente',
            }
        )
        
        notificaciones_enviadas += 1
        usuarios_notificados.add(usuario_id)
    
    logger.info(
        f"Trabajos finalizados: {count} | "
        f"IDs: {ids_finalizados} | "
        f"Notificaciones enviadas: {notificaciones_enviadas} | "
        f"Usuarios afectados: {len(usuarios_notificados)}"
    )
    
    return {
        'finalizados': count,
        'ids': ids_finalizados,
        'limite': limite.isoformat(),
        'notificaciones_enviadas': notificaciones_enviadas,
        'usuarios_afectados': len(usuarios_notificados),
    }