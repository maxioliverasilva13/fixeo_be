from localizacion.utils import calcular_distancia_km
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from usuario.utils import obtener_localizacion_usuario
from .models import Empresa
from .serializers import EmpresaSerializer
from .utils import validar_nombre_empresa_unico
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from .models import Producto
from .serializers import ProductoSerializer

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

    @action(detail=True, methods=['get'], url_path='distance-from-me')
    def distance_from_me(self, request, pk=None):
        empresa = self.get_object()
        usuario = request.user

        loc_usuario = obtener_localizacion_usuario(usuario)
        if not loc_usuario:
            return Response(
                {'error': 'El usuario no tiene localización configurada'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not empresa.localizacion:
            return Response(
                {'error': 'La empresa no tiene localización configurada'},
                status=status.HTTP_400_BAD_REQUEST
            )

        loc_empresa = empresa.localizacion

        distancia = calcular_distancia_km(
            loc_usuario.latitud,
            loc_usuario.longitud,
            loc_empresa.latitud,
            loc_empresa.longitud
        )

        return Response({
            'empresa_id': empresa.id,
            'empresa_nombre': empresa.nombre,
            'distance_km': distancia,
            'user_location': {
                'city': loc_usuario.city,
                'country': loc_usuario.country
            },
            'empresa_location': {
                'city': loc_empresa.city,
                'country': loc_empresa.country
            }
        })
    
class ProductoViewSet(viewsets.ModelViewSet):
    queryset = Producto.objects.all()
    serializer_class = ProductoSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        queryset = super().get_queryset()
        empresa_id = self.request.query_params.get('empresa_id', None)
        disponible = self.request.query_params.get('disponible', None)

        if empresa_id:
            queryset = queryset.filter(empresa_id=empresa_id)
        if disponible is not None:
            queryset = queryset.filter(disponible=disponible.lower() == 'true')

        return queryset

    def create(self, request, *args, **kwargs):
        empresa_id = request.data.get('empresa')
        if not empresa_id:
            return Response(
                {'error': 'El campo empresa es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        from .models import Empresa
        try:
            empresa = Empresa.objects.get(id=empresa_id)
        except Empresa.DoesNotExist:
            return Response({'error': 'Empresa no encontrada'}, status=status.HTTP_404_NOT_FOUND)

        if empresa.admin_id != request.user:
            return Response({'error': 'No tenés permisos para agregar productos a esta empresa'}, status=status.HTTP_403_FORBIDDEN)

        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.empresa.admin_id != request.user:
            return Response({'error': 'No tenés permisos para modificar este producto'}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.empresa.admin_id != request.user:
            return Response({'error': 'No tenés permisos para eliminar este producto'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['patch'], url_path='toggle-disponible')
    def toggle_disponible(self, request, pk=None):
        producto = self.get_object()
        if producto.empresa.admin_id != request.user:
            return Response({'error': 'No tenés permisos'}, status=status.HTTP_403_FORBIDDEN)
        producto.disponible = not producto.disponible
        producto.save()
        return Response({'id': producto.id, 'disponible': producto.disponible})