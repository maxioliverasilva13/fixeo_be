from disponibilidad.models import Disponibilidad, Tipo
from datetime import datetime, timedelta
from django.utils.timezone import make_aware
from empresas.models import Horarios


def hay_conflicto(usuario_id, inicio, fin):
    return Disponibilidad.objects.filter(
        usuario_id=usuario_id,
        tipo__in=[Tipo.OCUPADO, Tipo.BLOQUEADO],
        fecha_inicio__lt=fin,
        fecha_fin__gt=inicio
    ).exists()


def calcular_duracion_servicios(servicios):
    return sum(s.tiempo for s in servicios)

def rango_horario_empresa(usuario, fecha):
    """
    Devuelve (inicio, fin) del horario de la empresa
    para esa fecha o None si no hay horario
    """
    empresa = usuario.empresas_administradas.first()
    if not empresa:
        return None
    
    dia_semana = str(fecha.isoweekday())

    horario = Horarios.objects.filter(
        empresa=empresa,
        dia_semana=dia_semana,
        enabled=True
    ).first()
    
    if not horario:
        return None
    
    inicio = make_aware(datetime.combine(fecha.date(), horario.hora_inicio))
    fin = make_aware(datetime.combine(fecha.date(), horario.hora_fin))
    
    return inicio, fin


def calcular_rango(fecha, hora, duracion_min):
    inicio = datetime.combine(fecha, hora)
    fin = inicio + timedelta(minutes=duracion_min)
    return make_aware(inicio), make_aware(fin)


def hay_solapamiento(profesional, inicio, fin):
    return Disponibilidad.objects.filter(
        profesional=profesional,
        estado=Tipo.OCUPADO,
        hora_inicio__lt=fin,
        hora_fin__gt=inicio
    ).exists()