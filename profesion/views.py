from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from notificaciones.tasks import notificar_usuario as notificar_usuario_task
from .models import DeviceToken, Notificaciones, Notas
from .serializers import (
    DeviceTokenCreateSerializer,
    DeviceTokenSerializer,
    NotificacionesSerializer,
    NotasSerializer,
)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


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
        device_name = request.data.get('device_name')
        device_token = request.data.get('device_token')

        if not device_token:
            return Response(
                {'error': 'device_token es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )

        existing_token = DeviceToken.objects.filter(
            device_token=device_token,
            usuario=request.user
        ).first()

        if existing_token:
            existing_token.device_name = device_name or existing_token.device_name
            existing_token.enabled = True
            existing_token.save()
            serializer = DeviceTokenSerializer(existing_token)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = DeviceTokenCreateSerializer(data={
            'device_name': device_name,
            'device_token': device_token,
        })
        serializer.is_valid(raise_exception=True)
        serializer.save(usuario=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='notificar-usuario')
    def notificar_usuario(self, request):
        usuario_id = request.data.get('usuario_id', None)
        if usuario_id:
            notificar_usuario_task.delay(
                usuario_id=usuario_id,
                titulo="Nueva notificación",
                mensaje="Tienes una nueva notificación"
            )
        return Response({'message': 'Notificación enviada'}, status=status.HTTP_200_OK)


class NotificacionesViewSet(viewsets.ModelViewSet):
    queryset = Notificaciones.objects.all()
    serializer_class = NotificacionesSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        usuario_id = self.request.query_params.get("usuario_id", None)
        if usuario_id:
            queryset = queryset.filter(usuario_id=usuario_id)
        return queryset.order_by("-created_at")

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = self.get_serializer(page, many=True)
        return Response({
            "count":    paginator.page.paginator.count,
            "next":     paginator.get_next_link(),
            "previous": paginator.get_previous_link(),
            "results":  serializer.data,
        })


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