from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from empresas.models import Horarios
from .serializers import HorariosSerializer
from rest_framework.decorators import action
from django.db import transaction
from rest_framework.response import Response
from rest_framework import viewsets, status
from empresas.models import Empresa

class HorariosViewSet(viewsets.ModelViewSet):
    queryset = Horarios.objects.all()
    serializer_class = HorariosSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        empresa_id = self.request.query_params.get('empresa_id', None)
        if empresa_id:
            queryset = queryset.filter(empresa_id=empresa_id)
        return queryset

    @action(detail=False, methods=['post'])
    def bulk(self, request):
        try:
            empresa = Empresa.objects.get(admin_id=request.user)
        except Empresa.DoesNotExist:
            return Response(
                {'error': 'No se encontró una empresa asociada a tu cuenta'},
                status=status.HTTP_404_NOT_FOUND,
            )

        horarios_data = request.data
        dias_recibidos = []

        # ValidationError (ej. "hora_inicio debe ser menor que hora_fin") se
        # deja propagar sin atrapar: antes un `except Exception` genérico la
        # disfrazaba de error 500 ("Error al obtener la empresa...") en vez
        # de devolver el 400 con el motivo real que el serializer ya arma.
        with transaction.atomic():
            for item in horarios_data:
                serializer = HorariosSerializer(data=item)
                serializer.is_valid(raise_exception=True)

                dia = serializer.validated_data['dia_semana']
                dias_recibidos.append(dia)

                qs = Horarios.objects.filter(empresa=empresa, dia_semana=dia)

                if qs.exists():
                    qs.delete()

                Horarios.objects.create(
                    empresa=empresa,
                    dia_semana=dia,
                    hora_inicio=serializer.validated_data["hora_inicio"],
                    hora_fin=serializer.validated_data["hora_fin"],
                    enabled=serializer.validated_data.get("enabled", True),
                )

        Horarios.objects.filter(
            empresa=empresa
        ).exclude(
            dia_semana__in=dias_recibidos
        ).delete()
        return Response({"ok": True})