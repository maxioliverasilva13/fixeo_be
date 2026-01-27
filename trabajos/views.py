from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Trabajo, Calificacion, Estados
from .serializers import TrabajoSerializer, CalificacionSerializer, EstadosSerializer


class TrabajoViewSet(viewsets.ModelViewSet):
    queryset = Trabajo.objects.all()
    serializer_class = TrabajoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        usuario_id = self.request.query_params.get('usuario_id', None)
        estado = self.request.query_params.get('estado', None)
        
        if usuario_id:
            queryset = queryset.filter(usuario_id=usuario_id)
        if estado:
            queryset = queryset.filter(estado=estado)
        
        return queryset


class CalificacionViewSet(viewsets.ModelViewSet):
    queryset = Calificacion.objects.all()
    serializer_class = CalificacionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        user_cal_recibe = self.request.query_params.get('user_cal_recibe', None)
        trabajo_id = self.request.query_params.get('trabajo_id', None)
        
        if user_cal_recibe:
            queryset = queryset.filter(user_cal_recibe=user_cal_recibe)
        if trabajo_id:
            queryset = queryset.filter(trabajo_id=trabajo_id)
        
        return queryset


class EstadosViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Estados.objects.all()
    serializer_class = EstadosSerializer
    permission_classes = [IsAuthenticated]

