from celery import shared_task
from django.utils import timezone
from django.db import transaction
from .models import Trabajo


@shared_task(bind=True, max_retries=3)
def finalizar_trabajo(self, trabajo_id):
    try:
        with transaction.atomic():
            trabajo = Trabajo.objects.select_for_update().get(id=trabajo_id)

            if trabajo.status != "aceptado":
                return {
                    "success": False,
                    "reason": f"Trabajo en estado {trabajo.status}"
                }

            trabajo.status = "finalizado"
            trabajo.fecha_fin = timezone.now()
            trabajo.save(update_fields=["status", "fecha_fin", "updated_at"])

            return {
                "success": True,
                "trabajo_id": trabajo_id
            }

    except Trabajo.DoesNotExist:
        return {
            "success": False,
            "reason": "Trabajo no existe"
        }

    except Exception as exc:
        raise self.retry(exc=exc, countdown=10)