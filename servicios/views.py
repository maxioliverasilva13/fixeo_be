from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Servicio
from .serializers import ServicioSerializer, ServicioCreateSerializer


class ServicioViewSet(viewsets.ModelViewSet):
    serializer_class = ServicioSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Servicio.objects.filter(usuario=self.request.user)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ServicioCreateSerializer
        return ServicioSerializer
    
    @action(detail=True, methods=['get'], url_path='obtener-servicios')
    def obtener_servicios(self, request, pk=None):
        servicios = (
            Servicio.objects
            .filter(usuario_id=pk)
            .select_related('profesion')
            .order_by('profesion__nombre')
        )

        serializer = ServicioSerializer(servicios, many=True)
        return Response(serializer.data)
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        profesion_id = serializer.validated_data['profesion'].id
        nombre = serializer.validated_data['nombre']
        
        if not request.user.usuario_profesiones.filter(profesion_id=profesion_id).exists():
            return Response(
                {'error': 'No puedes crear un servicio para una profesión que no tienes asignada'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if Servicio.objects.filter(
            usuario=request.user,
            profesion_id=profesion_id,
            nombre=nombre
        ).exists():
            return Response(
                {'error': f'Ya existe un servicio con el nombre "{nombre}" para esta profesión'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        servicio = serializer.save(usuario=request.user)
        
        return Response(
            ServicioSerializer(servicio).data,
            status=status.HTTP_201_CREATED
        )
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        if instance.usuario != request.user:
            return Response(
                {'error': 'No tienes permiso para editar este servicio'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = ServicioCreateSerializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        profesion_id = serializer.validated_data.get('profesion', instance.profesion).id
        nombre = serializer.validated_data.get('nombre', instance.nombre)
        
        if 'profesion' in serializer.validated_data:
            if profesion_id != instance.profesion_id:
                if not request.user.usuario_profesiones.filter(profesion_id=profesion_id).exists():
                    return Response(
                        {'error': 'No puedes asignar una profesión que no tienes'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        
        if Servicio.objects.filter(
            usuario=request.user,
            profesion_id=profesion_id,
            nombre=nombre
        ).exclude(id=instance.id).exists():
            return Response(
                {'error': f'Ya existe un servicio con el nombre "{nombre}" para esta profesión'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        servicio = serializer.save()
        
        return Response(ServicioSerializer(servicio).data)
    
    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Verificar que el servicio pertenece al usuario
        if instance.usuario != request.user:
            return Response(
                {'error': 'No tienes permiso para eliminar este servicio'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        profesion_nombre = instance.profesion.nombre
        instance.delete()
        
        return Response(
            {'message': f'Servicio de {profesion_nombre} eliminado exitosamente'},
            status=status.HTTP_200_OK
        )
    
    @action(detail=False, methods=['get'], url_path='por-profesion/(?P<profesion_id>[^/.]+)')
    def por_profesion(self, request, profesion_id=None):
        """
        Obtiene el servicio del usuario logueado para una profesión específica
        """
        try:
            servicio = Servicio.objects.get(usuario=request.user, profesion_id=profesion_id)
            serializer = self.get_serializer(servicio)
            return Response(serializer.data)
        except Servicio.DoesNotExist:
            return Response(
                {'error': 'No tienes un servicio configurado para esta profesión'},
                status=status.HTTP_404_NOT_FOUND
            )
