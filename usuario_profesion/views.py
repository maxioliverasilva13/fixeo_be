from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from .models import UsuarioProfesion, Profesion
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

    @action(detail=False, methods=['post'], url_path='actualizar')
    def actualizar(self, request):
        """
        Actualiza las profesiones del usuario autenticado.
        Recibe una lista de profesion_ids (máximo 3).
        Reemplaza completamente las profesiones existentes.
        """
        usuario = request.user
        profesion_ids = request.data.get('profesion_ids', [])
        
        if not isinstance(profesion_ids, list):
            return Response(
                {'error': 'profesion_ids debe ser una lista'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(profesion_ids) > 3:
            return Response(
                {'error': 'Máximo 3 profesiones permitidas'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            profesion_ids = [int(pid) for pid in profesion_ids]
        except (ValueError, TypeError):
            return Response(
                {'error': 'Todos los profesion_ids deben ser números enteros válidos'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        profesiones_existentes = Profesion.objects.filter(id__in=profesion_ids)
        if len(profesiones_existentes) != len(profesion_ids):
            return Response(
                {'error': 'Una o más profesiones no existen'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            UsuarioProfesion.objects.filter(usuario=usuario).delete()
            
            nuevas_profesiones = [
                UsuarioProfesion(usuario=usuario, profesion_id=pid)
                for pid in profesion_ids
            ]
            UsuarioProfesion.objects.bulk_create(nuevas_profesiones)
            
            usuario_profesiones = UsuarioProfesion.objects.filter(
                usuario=usuario
            ).select_related('profesion')
        
        serializer = self.get_serializer(usuario_profesiones, many=True)
        
        return Response({
            'message': 'Profesiones actualizadas correctamente',
            'profesiones': serializer.data,
            'total': len(profesion_ids)
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='mis-profesiones')
    def mis_profesiones(self, request):
        """
        Obtiene las profesiones del usuario autenticado.
        """
        usuario = request.user
        usuario_profesiones = UsuarioProfesion.objects.filter(
            usuario=usuario
        ).select_related('profesion')
        
        serializer = self.get_serializer(usuario_profesiones, many=True)
        
        return Response({
            'profesiones': serializer.data,
            'total': len(serializer.data)
        })