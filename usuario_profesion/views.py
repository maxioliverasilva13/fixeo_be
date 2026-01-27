from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import UsuarioProfesion
from .serializers import UsuarioProfesionSerializer


class UsuarioProfesionViewSet(viewsets.ModelViewSet):
    queryset = UsuarioProfesion.objects.all()
    serializer_class = UsuarioProfesionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        usuario_id = self.request.query_params.get('usuario_id', None)
        if usuario_id:
            queryset = queryset.filter(usuario_id=usuario_id)
        return queryset
