from disponibilidad.models import Disponibilidad


def hay_conflicto(usuario_id, inicio, fin):
    return Disponibilidad.objects.filter(
        usuario_id=usuario_id,
        tipo__in=['ocupado', 'bloqueado'],
        fecha_inicio__lt=fin,
        fecha_fin__gt=inicio
    ).exists()


def calcular_duracion_servicios(servicios):
    return sum(s.tiempo for s in servicios)
