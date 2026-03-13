from localizacion.utils import calcular_distancia_km
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from usuario.utils import obtener_localizacion_usuario
from .models import Empresa, CategoriaProducto, Producto
from .serializers import EmpresaSerializer, CategoriaProductoSerializer, ProductoSerializer
from .utils import validar_nombre_empresa_unico
from rest_framework.decorators import action


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


class CategoriaProductoViewSet(viewsets.ModelViewSet):
    queryset = CategoriaProducto.objects.all()
    serializer_class = CategoriaProductoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        empresa_id = self.request.query_params.get('empresa_id', None)
        
        if empresa_id:
            queryset = queryset.filter(empresa_id=empresa_id)
        else:
            empresas_usuario = Empresa.objects.filter(admin_id=self.request.user)
            queryset = queryset.filter(empresa__in=empresas_usuario)
        
        return queryset

    def perform_create(self, serializer):
        empresa_id = self.request.data.get('empresa')
        empresa = Empresa.objects.filter(id=empresa_id, admin_id=self.request.user).first()
        
        if not empresa:
            raise serializers.ValidationError({'error': 'No tienes permisos para crear categorías en esta empresa'})
        
        serializer.save()

    def perform_update(self, serializer):
        empresa = serializer.instance.empresa
        
        if empresa.admin_id != self.request.user:
            raise serializers.ValidationError({'error': 'No tienes permisos para modificar esta categoría'})
        
        serializer.save()

    def perform_destroy(self, instance):
        if instance.empresa.admin_id != self.request.user:
            raise serializers.ValidationError({'error': 'No tienes permisos para eliminar esta categoría'})
        
        instance.delete()


class ProductoViewSet(viewsets.ModelViewSet):
    queryset = Producto.objects.all()
    serializer_class = ProductoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        empresa_id = self.request.query_params.get('empresa_id', None)
        categoria_id = self.request.query_params.get('categoria_id', None)
        
        if empresa_id:
            queryset = queryset.filter(empresa_id=empresa_id)
        
        if categoria_id:
            queryset = queryset.filter(categoria_id=categoria_id)
        
        if not empresa_id and not categoria_id:
            empresas_usuario = Empresa.objects.filter(admin_id=self.request.user)
            queryset = queryset.filter(empresa__in=empresas_usuario)
        
        return queryset.select_related('empresa', 'categoria')

    def perform_create(self, serializer):
        empresa_id = self.request.data.get('empresa')
        empresa = Empresa.objects.filter(id=empresa_id, admin_id=self.request.user).first()
        
        if not empresa:
            raise serializers.ValidationError({'error': 'No tienes permisos para crear productos en esta empresa'})
        
        serializer.save()

    def perform_update(self, serializer):
        empresa = serializer.instance.empresa
        
        if empresa.admin_id != self.request.user:
            raise serializers.ValidationError({'error': 'No tienes permisos para modificar este producto'})
        
        serializer.save()

    def perform_destroy(self, instance):
        if instance.empresa.admin_id != self.request.user:
            raise serializers.ValidationError({'error': 'No tienes permisos para eliminar este producto'})
        
        instance.delete()
