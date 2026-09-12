from disponibilidad.models import Disponibilidad, Tipo
from datetime import datetime, timedelta
from calendar import monthrange
from django.utils.timezone import make_aware
from django.utils import timezone
from empresas.models import Horarios


def _bloques_del_dia(usuario, inicio_dia, fin_dia, inicio_empresa, fin_empresa):
    """Bloques 'disponible' explícitos del día; si no hay, todo el horario de empresa.

    Semántica del producto: si NO hay filas de disponibilidad para el día, el
    profesional está libre en todo el horario de su empresa.
    """
    bloques_qs = Disponibilidad.objects.filter(
        usuario=usuario, tipo='disponible',
        fecha_inicio__lt=fin_dia, fecha_fin__gt=inicio_dia,
    )
    if bloques_qs.exists():
        return list(bloques_qs)
    return [{'fecha_inicio': inicio_empresa, 'fecha_fin': fin_empresa}]


def horas_disponibles(usuario, fecha, duracion_min, step_minutes=15):
    """Slots [{hora, disponible}] para un día ('YYYY-MM-DD').

    Horario de empresa menos conflictos (OCUPADO/BLOQUEADO/trabajos aceptados).
    Misma lógica que el endpoint horas_disponibles_dia (que el frontend consume).
    """
    inicio_dia = make_aware(datetime.fromisoformat(f"{fecha}T00:00:00"))
    fin_dia = make_aware(datetime.fromisoformat(f"{fecha}T23:59:59"))
    now = timezone.now()
    if fin_dia < now:
        return []

    rango_empresa = rango_horario_empresa(usuario, inicio_dia)
    if not rango_empresa:
        return []
    inicio_empresa, fin_empresa = rango_empresa

    bloques = _bloques_del_dia(usuario, inicio_dia, fin_dia, inicio_empresa, fin_empresa)
    slots = []
    for bloque in bloques:
        bloque_inicio = bloque.fecha_inicio if hasattr(bloque, 'fecha_inicio') else bloque['fecha_inicio']
        bloque_fin = bloque.fecha_fin if hasattr(bloque, 'fecha_fin') else bloque['fecha_fin']

        if inicio_dia.date() == now.date():
            current = max(bloque_inicio, inicio_empresa, now)
        else:
            current = max(bloque_inicio, inicio_empresa)
        fin_real = min(bloque_fin, fin_empresa)

        while True:
            fin_slot = current + timedelta(minutes=duracion_min)
            if fin_slot > fin_real:
                break
            disponible = not hay_conflicto(usuario_id=usuario.id, inicio=current, fin=fin_slot)
            slots.append({
                'hora': timezone.localtime(current).strftime('%H:%M'),
                'disponible': disponible,
            })
            current += timedelta(minutes=step_minutes)
    return slots


def dias_disponibles(usuario, year, month, duracion_min):
    """Lista de días del mes con al menos un hueco para un servicio de `duracion_min`."""
    _, last_day = monthrange(year, month)
    dias = []
    now = timezone.now()

    for day in range(1, last_day + 1):
        inicio_dia = make_aware(datetime(year, month, day, 0, 0))
        fin_dia = make_aware(datetime(year, month, day, 23, 59, 59))
        if fin_dia < now:
            continue

        rango_empresa = rango_horario_empresa(usuario, inicio_dia)
        if not rango_empresa:
            continue
        inicio_empresa, fin_empresa = rango_empresa

        bloques = _bloques_del_dia(usuario, inicio_dia, fin_dia, inicio_empresa, fin_empresa)
        for bloque in bloques:
            bloque_inicio = bloque.fecha_inicio if hasattr(bloque, 'fecha_inicio') else bloque['fecha_inicio']
            bloque_fin = bloque.fecha_fin if hasattr(bloque, 'fecha_fin') else bloque['fecha_fin']

            if inicio_dia.date() == now.date():
                inicio_real = max(bloque_inicio, inicio_empresa, now)
            else:
                inicio_real = max(bloque_inicio, inicio_empresa)
            fin_real = min(bloque_fin, fin_empresa)
            if inicio_real >= fin_real:
                continue

            minutos_libres = int((fin_real - inicio_real).total_seconds() / 60)
            if minutos_libres >= duracion_min:
                dias.append(day)
                break
    return dias


def hay_conflicto(usuario_id, inicio, fin):
    """
    Verifica si hay conflicto de horario para un usuario.
    Solo considera conflicto si:
    - Es una disponibilidad OCUPADA o BLOQUEADA
    - Si viene de un trabajo, solo si el trabajo está 'aceptado' o 'finalizado'
    - Los trabajos 'pendiente' o 'cancelado' NO cuentan como conflicto
    """
    from trabajos.models import Trabajo
    
    disponibilidades_conflicto = Disponibilidad.objects.filter(
        usuario_id=usuario_id,
        tipo__in=[Tipo.OCUPADO, Tipo.BLOQUEADO],
        fecha_inicio__lt=fin,
        fecha_fin__gt=inicio
    )
    
    for disp in disponibilidades_conflicto:
        if disp.origen != 'trabajo':
            return True
        
        trabajo = disp.trabajos.first()
        
        if not trabajo:
            return True
        
        if trabajo.status in ['aceptado', 'finalizado']:
            return True
        
    
    return False


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