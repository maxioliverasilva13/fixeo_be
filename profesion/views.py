from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from .models import Profesion
from .serializers import ProfesionSerializer
from usuario_profesion.models import UsuarioProfesion


class ProfesionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Profesion.objects.all()
    serializer_class = ProfesionSerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=['get'])
    def buscar(self, request):
        texto = request.query_params.get('texto', '')
        limit = int(request.query_params.get('limit', 10))
        offset = int(request.query_params.get('offset', 0))
        
        if limit > 100:
            limit = 100
        
        queryset = Profesion.objects.all()
        
        if texto:
            queryset = queryset.filter(
                Q(nombre__icontains=texto) | Q(descripcion__icontains=texto)
            )
        
        total = queryset.count()
        profesiones = queryset[offset:offset + limit]
        
        serializer = self.get_serializer(profesiones, many=True)
        
        return Response({
            'total': total,
            'limit': limit,
            'offset': offset,
            'results': serializer.data
        })


class AdminProfesionViewSet(viewsets.ModelViewSet):
    queryset = Profesion.objects.all()
    serializer_class = ProfesionSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = None

    def destroy(self, request, *args, **kwargs):
        profesion = self.get_object()
        with transaction.atomic():
            UsuarioProfesion.objects.filter(profesion=profesion).update(
                is_deleted=True, deleted_at=timezone.now(), deleted_by=request.user
            )
            profesion.is_deleted = True
            profesion.deleted_at = timezone.now()
            profesion.deleted_by = request.user
            profesion.save(update_fields=['is_deleted', 'deleted_at', 'deleted_by'])
        return Response({'message': 'Profesión eliminada correctamente'}, status=status.HTTP_200_OK)
