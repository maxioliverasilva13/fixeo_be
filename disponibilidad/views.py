from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import Disponibilidad
from .serializers import DisponibilidadSerializer


class DisponibilidadViewSet(viewsets.ModelViewSet):
    queryset = Disponibilidad.objects.all()
    serializer_class = DisponibilidadSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        usuario_id = self.request.query_params.get('usuario_id', None)
        if usuario_id:
            queryset = queryset.filter(usuario_id=usuario_id)
        return queryset
