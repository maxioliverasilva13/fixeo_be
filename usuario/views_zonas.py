from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import ZonaNoTrabajo
from .serializers_zonas import ZonaNoTrabajoSerializer


class ZonaNoTrabajoViewSet(viewsets.ModelViewSet):
    serializer_class = ZonaNoTrabajoSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        return ZonaNoTrabajo.objects.filter(usuario=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        if not self.request.user.is_owner_empresa:
            raise PermissionError
        serializer.save(usuario=self.request.user)

    def create(self, request, *args, **kwargs):
        if not request.user.is_owner_empresa:
            return Response(
                {'error': 'Solo los profesionales pueden configurar zonas de exclusión.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        if not request.user.is_owner_empresa:
            return Response(
                {'error': 'Solo los profesionales pueden configurar zonas de exclusión.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if not request.user.is_owner_empresa:
            return Response(
                {'error': 'Solo los profesionales pueden configurar zonas de exclusión.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)
