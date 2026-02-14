from celery import shared_task
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@shared_task(name='fixeo_project.tasks.test_celery_beat')
def test_celery_beat():
    """
    Tarea de prueba que se ejecuta cada minuto para verificar que Celery está funcionando.
    """
    timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
    mensaje = f"🔥 [CELERY BEAT TEST] Tarea ejecutada exitosamente a las {timestamp}"
    
    logger.info(mensaje)
    print(mensaje)
    
    return {
        'status': 'success',
        'timestamp': timestamp,
        'message': 'Celery Beat está funcionando correctamente'
    }


@shared_task(name='fixeo_project.tasks.test_celery_worker')
def test_celery_worker(mensaje="Test manual"):
    """
    Tarea manual para probar que el worker está procesando tareas.
    Puedes ejecutarla desde Django shell con:
    >>> from fixeo_project.tasks import test_celery_worker
    >>> test_celery_worker.delay("Mi mensaje de prueba")
    """
    timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
    resultado = f"⚡ [CELERY WORKER TEST] {mensaje} - Ejecutado a las {timestamp}"
    
    logger.info(resultado)
    print(resultado)
    
    return {
        'status': 'success',
        'timestamp': timestamp,
        'mensaje_original': mensaje,
        'message': 'Worker procesó la tarea correctamente'
    }
