from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import Plan, Subscripcion
from .serializers import PlanSerializer, SubscripcionSerializer


class PlanViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Plan.objects.filter(activo=True).order_by('precio')
    serializer_class = PlanSerializer
    permission_classes = [AllowAny]
    
    def list(self, request, *args, **kwargs):
        """
        Obtiene el listado de todos los planes disponibles
        No requiere autenticación
        """
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class SubscripcionViewSet(viewsets.ModelViewSet):
    queryset = Subscripcion.objects.all()
    serializer_class = SubscripcionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        user_id = self.request.query_params.get('user_id', None)
        cancelada = self.request.query_params.get('cancelada', None)
        
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        if cancelada is not None:
            queryset = queryset.filter(cancelada=cancelada.lower() == 'true')
        
        return queryset.order_by('-created_at')

