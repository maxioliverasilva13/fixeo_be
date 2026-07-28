from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .models import Publicidad
from .serializers import PublicidadSerializer


class PublicidadAdminViewSet(viewsets.ModelViewSet):
    queryset = Publicidad.objects.all()
    serializer_class = PublicidadSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    @action(detail=True, methods=['patch'], url_path='cerrar')
    def cerrar(self, request, pk=None):
        publicidad = self.get_object()
        publicidad.activa = False
        publicidad.save(update_fields=['activa'])
        return Response(PublicidadSerializer(publicidad).data, status=status.HTTP_200_OK)


class PublicidadActivasViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PublicidadSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Publicidad.objects.filter(activa=True).filter(
            Q(fecha_expiracion__isnull=True) | Q(fecha_expiracion__gt=timezone.now())
        )

        rol_nombre = getattr(self.request.user.rol, 'nombre', None)
        if rol_nombre:
            qs = qs.filter(Q(dirigido_a='ambos') | Q(dirigido_a=rol_nombre))
        else:
            qs = qs.filter(dirigido_a='ambos')

        return qs.order_by('orden', '-created_at')
