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
        empresa = Empresa.objects.get(admin_id=request.user)

        horarios_data = request.data
        dias_recibidos = []

        with transaction.atomic():
            for item in horarios_data:
                serializer = HorariosSerializer(data=item)
                serializer.is_valid(raise_exception=True)

                dia = serializer.validated_data['dia_semana']
                dias_recibidos.append(dia)

                Horarios.objects.update_or_create(
                    empresa=empresa,
                    dia_semana=dia,
                    defaults={
                        "hora_inicio": serializer.validated_data["hora_inicio"],
                        "hora_fin": serializer.validated_data["hora_fin"],
                        "enabled": serializer.validated_data.get("enabled", True),
                    }
                )

            Horarios.objects.filter(
                empresa=empresa
            ).exclude(
                dia_semana__in=dias_recibidos
            ).delete()


        return Response({"ok": True})