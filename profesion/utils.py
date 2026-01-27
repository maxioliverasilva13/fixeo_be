from .models import Profesion


def obtener_profesion_por_id(profesion_id):
    try:
        return Profesion.objects.get(id=profesion_id)
    except Profesion.DoesNotExist:
        return None


def obtener_profesiones_por_ids(profesion_ids):
    return Profesion.objects.filter(id__in=profesion_ids)
