from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from notificaciones.tasks import notificar_usuario as notificar_usuario_task
from .device_token_service import activate_device_token_for_user
from .models import DeviceToken, Notificaciones, Notas
from .serializers import DeviceTokenSerializer, NotificacionesSerializer, NotasSerializer

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
        device_name = request.data.get('device_name') or 'Fixeo App'
        device_token = request.data.get('device_token')

        if not device_token:
            return Response(
                {'error': 'device_token es requerido'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # El mismo token FCM puede existir para varios usuarios (historial),
        # pero solo el usuario logueado en el dispositivo lo tiene enabled=True.
        token_obj, created = activate_device_token_for_user(
            usuario=request.user,
            device_token=device_token,
            device_name=device_name,
        )
        serializer = DeviceTokenSerializer(token_obj)
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(serializer.data, status=status_code)

    @action(detail=False, methods=['post'], url_path='notificar-usuario')
    def notificar_usuario(self, request):
        usuario_id = request.data.get('usuario_id', None)
        if usuario_id:
            notificar_usuario_task.delay(usuario_id=usuario_id, titulo="Nueva notificación", mensaje="Tienes una nueva notificación")
        return Response({'message': 'Notificación enviada'}, status=status.HTTP_200_OK)

class NotificacionesViewSet(viewsets.ModelViewSet):
    serializer_class = NotificacionesSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Notificaciones.objects.filter(
            usuario=self.request.user
        ).order_by('-created_at')

        leida = self.request.query_params.get('leida', None)
        if leida is not None:
            qs = qs.filter(leida=leida.lower() == 'true')

        return qs

    @action(detail=True, methods=['patch'], url_path='marcar-leida')
    def marcar_leida(self, request, pk=None):
        notificacion = self.get_object()
        if notificacion.usuario != request.user:
            return Response({'error': 'No tenés permisos'}, status=status.HTTP_403_FORBIDDEN)
        notificacion.leida = True          
        notificacion.save(update_fields=['leida'])
        return Response({'ok': True})

    @action(detail=False, methods=['patch'], url_path='marcar-todas-leidas')
    def marcar_todas_leidas(self, request):
        Notificaciones.objects.filter(
            usuario=request.user,
            leida=False           
        ).update(leida=True)
        return Response({'ok': True})

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

