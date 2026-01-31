from disponibilidad.utils import calcular_duracion_servicios, hay_conflicto
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
    """
    Devuelve los días del mes donde entran TODOS los servicios seleccionados
    """
    usuario_id = request.data['usuario_id']
    servicios_ids = request.data['servicios_ids']
    year = request.data['year']
    month = request.data['month']

    servicios = Servicio.objects.filter(id__in=servicios_ids)
    duracion_total = calcular_duracion_servicios(servicios)

    _, last_day = monthrange(year, month)
    dias_disponibles = []

    for day in range(1, last_day + 1):
        inicio_dia = make_aware(datetime(year, month, day, 0, 0))
        fin_dia = make_aware(datetime(year, month, day, 23, 59, 59))

        bloques = Disponibilidad.objects.filter(
            usuario_id=usuario_id,
            tipo='disponible',
            fecha_inicio__lt=fin_dia,
            fecha_fin__gt=inicio_dia
        )

        for bloque in bloques:
            minutos_libres = int(
                (bloque.fecha_fin - bloque.fecha_inicio).total_seconds() / 60
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
    marcando si cada slot es usable o no
    """
    usuario_id = request.data['usuario_id']
    servicios_ids = request.data['servicios_ids']
    fecha = request.data['fecha']  # YYYY-MM-DD

    servicios = Servicio.objects.filter(id__in=servicios_ids)
    duracion_total = calcular_duracion_servicios(servicios)

    inicio_dia = make_aware(datetime.fromisoformat(f"{fecha}T00:00:00"))
    fin_dia = make_aware(datetime.fromisoformat(f"{fecha}T23:59:59"))

    bloques = Disponibilidad.objects.filter(
        usuario_id=usuario_id,
        tipo='disponible',
        fecha_inicio__lt=fin_dia,
        fecha_fin__gt=inicio_dia
    )

    STEP_MINUTES = 15
    slots = []

    for bloque in bloques:
        current = max(bloque.fecha_inicio, inicio_dia)

        while True:
            fin_slot = current + timedelta(minutes=duracion_total)

            if fin_slot > bloque.fecha_fin:
                break

            disponible = not hay_conflicto(
                usuario_id=usuario_id,
                inicio=current,
                fin=fin_slot
            )

            slots.append({
                "hora": current.strftime('%H:%M'),
                "disponible": disponible
            })

            current += timedelta(minutes=STEP_MINUTES)

    return Response({
        "fecha": fecha,
        "duracion_total_minutos": duracion_total,
        "horas": slots
    })
