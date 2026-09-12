from disponibilidad.utils import (
    calcular_duracion_servicios, hay_conflicto, rango_horario_empresa,
    horas_disponibles, dias_disponibles,
)
from rest_framework import viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
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
@permission_classes([AllowAny])
def dias_disponibles_mes(request):
    usuario_id = request.data['usuario_id']
    servicios_ids = request.data['servicios_ids']
    year = request.data['year']
    month = request.data['month']

    usuario = Usuario.objects.get(id=usuario_id)
    servicios = Servicio.objects.filter(id__in=servicios_ids)
    duracion_total = calcular_duracion_servicios(servicios)

    dias = dias_disponibles(usuario, year, month, duracion_total)

    return Response({
        "year": year,
        "month": month,
        "dias_disponibles": dias
    })

@api_view(['POST'])
@permission_classes([AllowAny])
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

    slots = horas_disponibles(usuario, fecha, duracion_total)

    return Response({
        "fecha": fecha,
        "duracion_total_minutos": duracion_total,
        "horas": slots
    })
