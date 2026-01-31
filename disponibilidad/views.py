from disponibilidad.utils import calcular_duracion_servicios, hay_conflicto, rango_horario_empresa
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Disponibilidad
from .serializers import DisponibilidadSerializer
from datetime import datetime, timedelta
from calendar import monthrange
from django.utils.timezone import make_aware
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from servicios.models import Servicio
from usuario.models import Usuario
from django.utils import timezone


class DisponibilidadViewSet(viewsets.ModelViewSet):
    queryset = Disponibilidad.objects.all()
    serializer_class = DisponibilidadSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        usuario_id = self.request.query_params.get('usuario_id')
        if usuario_id:
            queryset = queryset.filter(usuario_id=usuario_id)
        return queryset


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def dias_disponibles_mes(request):
    usuario_id = request.data['usuario_id']
    servicios_ids = request.data['servicios_ids']
    year = request.data['year']
    month = request.data['month']

    usuario = Usuario.objects.get(id=usuario_id)
    servicios = Servicio.objects.filter(id__in=servicios_ids)
    duracion_total = calcular_duracion_servicios(servicios)

    _, last_day = monthrange(year, month)
    dias_disponibles = []

    now = timezone.now()

    for day in range(1, last_day + 1):
        inicio_dia = timezone.make_aware(datetime(year, month, day, 0, 0))
        fin_dia = timezone.make_aware(datetime(year, month, day, 23, 59, 59))

        if fin_dia < now:
            continue

        rango_empresa = rango_horario_empresa(usuario, inicio_dia)
        if not rango_empresa:
            continue

        print(f"Rango de la empresa: {rango_empresa}")

        inicio_empresa, fin_empresa = rango_empresa

        bloques_qs = Disponibilidad.objects.filter(
            usuario=usuario,
            tipo='disponible',
            fecha_inicio__lt=fin_dia,
            fecha_fin__gt=inicio_dia
        )

        if bloques_qs.exists():
            bloques = bloques_qs
        else:
            bloques = [{
                "fecha_inicio": inicio_empresa,
                "fecha_fin": fin_empresa
            }]

        for bloque in bloques:
            bloque_inicio = (
                bloque.fecha_inicio if hasattr(bloque, 'fecha_inicio')
                else bloque['fecha_inicio']
            )
            bloque_fin = (
                bloque.fecha_fin if hasattr(bloque, 'fecha_fin')
                else bloque['fecha_fin']
            )

            # ⏱️ inicio real
            if inicio_dia.date() == now.date():
                inicio_real = max(bloque_inicio, inicio_empresa, now)
            else:
                inicio_real = max(bloque_inicio, inicio_empresa)

            fin_real = min(bloque_fin, fin_empresa)

            if inicio_real >= fin_real:
                continue

            minutos_libres = int(
                (fin_real - inicio_real).total_seconds() / 60
            )

            if minutos_libres >= duracion_total:
                dias_disponibles.append(day)
                break

    return Response({
        "year": year,
        "month": month,
        "dias_disponibles": dias_disponibles
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def horas_disponibles_dia(request):
    """
    Devuelve las horas posibles para un día específico,
    respetando:
    - horario de la empresa
    - disponibilidad
    - duración del servicio
    - conflictos
    - fecha/hora actual
    """
    usuario_id = request.data['usuario_id']
    servicios_ids = request.data['servicios_ids']
    fecha = request.data['fecha']  # YYYY-MM-DD

    usuario = Usuario.objects.get(id=usuario_id)
    servicios = Servicio.objects.filter(id__in=servicios_ids)
    duracion_total = calcular_duracion_servicios(servicios)

    inicio_dia = make_aware(datetime.fromisoformat(f"{fecha}T00:00:00"))
    fin_dia = make_aware(datetime.fromisoformat(f"{fecha}T23:59:59"))

    now = timezone.now()

    # ❌ día completamente pasado
    if fin_dia < now:
        return Response({
            "fecha": fecha,
            "duracion_total_minutos": duracion_total,
            "horas": []
        })

    rango_empresa = rango_horario_empresa(usuario, inicio_dia)
    if not rango_empresa:
        return Response({
            "fecha": fecha,
            "duracion_total_minutos": duracion_total,
            "horas": []
        })

    inicio_empresa, fin_empresa = rango_empresa

    bloques_qs = Disponibilidad.objects.filter(
        usuario=usuario,
        tipo='disponible',
        fecha_inicio__lt=fin_dia,
        fecha_fin__gt=inicio_dia
    )

    # 🔥 si no hay bloques → todo el horario empresa está libre
    if bloques_qs.exists():
        bloques = bloques_qs
    else:
        bloques = [{
            "fecha_inicio": inicio_empresa,
            "fecha_fin": fin_empresa
        }]

    STEP_MINUTES = 15
    slots = []

    for bloque in bloques:
        bloque_inicio = (
            bloque.fecha_inicio if hasattr(bloque, 'fecha_inicio')
            else bloque['fecha_inicio']
        )
        bloque_fin = (
            bloque.fecha_fin if hasattr(bloque, 'fecha_fin')
            else bloque['fecha_fin']
        )

        # ⏱️ inicio real
        if inicio_dia.date() == now.date():
            current = max(bloque_inicio, inicio_empresa, now)
        else:
            current = max(bloque_inicio, inicio_empresa)

        fin_real = min(bloque_fin, fin_empresa)

        while True:
            fin_slot = current + timedelta(minutes=duracion_total)

            if fin_slot > fin_real:
                break

            disponible = not hay_conflicto(
                usuario_id=usuario_id,
                inicio=current,
                fin=fin_slot
            )

            hora_local = timezone.localtime(current)
            slots.append({
                "hora": hora_local.strftime('%H:%M'),
                "disponible": disponible
            })

            current += timedelta(minutes=STEP_MINUTES)

    return Response({
        "fecha": fecha,
        "duracion_total_minutos": duracion_total,
        "horas": slots
    })
