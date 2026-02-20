from django.contrib.admin import action
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from .models import DeviceToken, Notificaciones, Notas
from .serializers import DeviceTokenCreateSerializer, DeviceTokenSerializer, NotificacionesSerializer, NotasSerializer

from rest_framework.response import Response

class DeviceTokenViewSet(viewsets.ModelViewSet):
    queryset = DeviceToken.objects.all()
    serializer_class = DeviceTokenSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        usuario_id = self.request.query_params.get('usuario_id', None)
        if usuario_id:
            queryset = queryset.filter(usuario_id=usuario_id)
        return queryset
    
    def create(self, request):
        serializer = DeviceTokenCreateSerializer(data={
            'device_name': request.data.get('device_name'),
            'device_token': request.data.get('device_token'),
        })
        serializer.is_valid(raise_exception=True)
        serializer.save(usuario=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class NotificacionesViewSet(viewsets.ModelViewSet):
    queryset = Notificaciones.objects.all()
    serializer_class = NotificacionesSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        usuario_id = self.request.query_params.get('usuario_id', None)
        if usuario_id:
            queryset = queryset.filter(usuario_id=usuario_id)
        return queryset.order_by('-created_at')


class NotasViewSet(viewsets.ModelViewSet):
    queryset = Notas.objects.all()
    serializer_class = NotasSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        estado = self.request.query_params.get('estado', None)
        if estado:
            queryset = queryset.filter(estado=estado)
        return queryset.order_by('-created_at')

