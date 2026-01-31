from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Empresa
from .serializers import EmpresaSerializer
from .utils import validar_nombre_empresa_unico


class EmpresaViewSet(viewsets.ModelViewSet):
    queryset = Empresa.objects.all()
    serializer_class = EmpresaSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        admin_id = self.request.query_params.get('admin_id', None)
        if admin_id:
            queryset = queryset.filter(admin_id=admin_id)
        return queryset
    
    def create(self, request, *args, **kwargs):
        nombre = request.data.get('nombre')
        if nombre and not validar_nombre_empresa_unico(nombre):
            return Response(
                {'error': f"Ya existe una empresa con el nombre '{nombre}'"},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().create(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        nombre = request.data.get('nombre')
        if nombre and nombre.lower() != instance.nombre.lower() and not validar_nombre_empresa_unico(nombre):
            return Response(
                {'error': f"Ya existe una empresa con el nombre '{nombre}'"},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().update(request, *args, **kwargs)
