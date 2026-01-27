from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from localizacion.models import Localizacion
from .models import UsuarioLocalizacion
from .serializers import UsuarioLocalizacionSerializer, UsuarioLocalizacionCreateSerializer


class UsuarioLocalizacionViewSet(viewsets.ModelViewSet):
    serializer_class = UsuarioLocalizacionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UsuarioLocalizacion.objects.filter(usuario=self.request.user).select_related('localizacion')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return UsuarioLocalizacionCreateSerializer
        return UsuarioLocalizacionSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        localizacion = Localizacion.objects.create(
            ubicacion=serializer.validated_data.get('ubicacion', ''),
            latitud=serializer.validated_data['latitud'],
            longitud=serializer.validated_data['longitud'],
            address=serializer.validated_data.get('address', ''),
            notas=serializer.validated_data.get('notas', ''),
            interior_door=serializer.validated_data.get('interior_door', ''),
            city=serializer.validated_data.get('city', ''),
            country=serializer.validated_data.get('country', ''),
            county=serializer.validated_data.get('county', ''),
            state=serializer.validated_data.get('state', '')
        )
        
        es_primera_localizacion = not UsuarioLocalizacion.objects.filter(usuario=request.user).exists()
        
        usuario_localizacion = UsuarioLocalizacion.objects.create(
            usuario=request.user,
            localizacion=localizacion,
            es_principal=serializer.validated_data.get('es_principal', es_primera_localizacion)
        )
        
        return Response(
            UsuarioLocalizacionSerializer(usuario_localizacion).data,
            status=status.HTTP_201_CREATED
        )
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        if instance.usuario != request.user:
            return Response(
                {'error': 'No tienes permiso para editar esta localización'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = UsuarioLocalizacionCreateSerializer(data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        localizacion = instance.localizacion
        for field in ['ubicacion', 'latitud', 'longitud', 'address', 'notas', 'interior_door', 'city', 'country', 'county', 'state']:
            if field in serializer.validated_data:
                setattr(localizacion, field, serializer.validated_data[field])
        localizacion.save()
        
        if 'es_principal' in serializer.validated_data:
            instance.es_principal = serializer.validated_data['es_principal']
            instance.save()
        
        return Response(UsuarioLocalizacionSerializer(instance).data)
    
    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        
        if instance.usuario != request.user:
            return Response(
                {'error': 'No tienes permiso para eliminar esta localización'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if instance.es_principal:
            otras_localizaciones = UsuarioLocalizacion.objects.filter(
                usuario=request.user
            ).exclude(id=instance.id).first()
            
            if otras_localizaciones:
                otras_localizaciones.es_principal = True
                otras_localizaciones.save()
        
        localizacion = instance.localizacion
        instance.delete()
        localizacion.delete()
        
        return Response(
            {'message': 'Localización eliminada exitosamente'},
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'])
    def marcar_principal(self, request, pk=None):
        usuario_localizacion = self.get_object()
        
        if usuario_localizacion.usuario != request.user:
            return Response(
                {'error': 'No tienes permiso para modificar esta localización'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        UsuarioLocalizacion.objects.filter(
            usuario=request.user,
            es_principal=True
        ).update(es_principal=False)
        
        usuario_localizacion.es_principal = True
        usuario_localizacion.save()
        
        return Response({
            'message': 'Localización marcada como principal',
            'data': UsuarioLocalizacionSerializer(usuario_localizacion).data
        })
