from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Q
from .models import Profesion
from .serializers import ProfesionSerializer


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
