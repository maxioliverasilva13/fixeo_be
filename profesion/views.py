from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from .models import Profesion
from .serializers import ProfesionSerializer, ProponerProfesionSerializer
from .signals import notificar_admins_profesion_pendiente
from usuario_profesion.models import UsuarioProfesion

# Ícono genérico usado como placeholder cuando un usuario propone una profesión
# nueva desde el registro (mismo ícono de fallback que ya usa el seed para
# categorías sin ícono propio).
DEFAULT_LOGO_URL = 'https://dibvhmpmocsmqvlemcqk.supabase.co/storage/v1/object/public/bucketFixea/iconsProfesiones/box-open.png'


class ProfesionViewSet(viewsets.ReadOnlyModelViewSet):
    # Rechazadas no se ofrecen para elegir/crear (ni en registro ni en el picker
    # de profesiones del perfil); pendientes sí, para no duplicar propuestas.
    queryset = Profesion.objects.exclude(estado=Profesion.ESTADO_RECHAZADA)
    serializer_class = ProfesionSerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=['get'])
    def buscar(self, request):
        texto = request.query_params.get('texto', '')
        limit = int(request.query_params.get('limit', 10))
        offset = int(request.query_params.get('offset', 0))

        if limit > 100:
            limit = 100

        queryset = self.get_queryset()

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

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def proponer(self, request):
        """Permite crear una profesión con sólo el nombre cuando no existe en el
        catálogo (típicamente desde el registro). Nace `pendiente` y notifica
        a los admins para que la revisen; si ya existe (activa) devuelve esa."""
        serializer = ProponerProfesionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        nombre = serializer.validated_data['nombre'].strip()

        existente = Profesion.objects.filter(nombre__iexact=nombre).first()
        if existente:
            if existente.estado == Profesion.ESTADO_RECHAZADA:
                existente.estado = Profesion.ESTADO_PENDIENTE
                existente.save(update_fields=['estado'])
                notificar_admins_profesion_pendiente(existente)
            return Response(ProfesionSerializer(existente).data, status=status.HTTP_200_OK)

        profesion = Profesion.objects.create(
            nombre=nombre,
            logo_svg_url=DEFAULT_LOGO_URL,
            estado=Profesion.ESTADO_PENDIENTE,
        )
        return Response(ProfesionSerializer(profesion).data, status=status.HTTP_201_CREATED)


class AdminProfesionViewSet(viewsets.ModelViewSet):
    queryset = Profesion.objects.all()
    serializer_class = ProfesionSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = None

    def get_queryset(self):
        qs = Profesion.objects.all().order_by('-created_at')
        estado = self.request.query_params.get('estado')
        if estado in dict(Profesion.ESTADO_CHOICES):
            qs = qs.filter(estado=estado)
        return qs

    @action(detail=True, methods=['patch'], url_path='estado')
    def actualizar_estado(self, request, pk=None):
        profesion = self.get_object()
        nuevo_estado = request.data.get('estado')
        if nuevo_estado not in dict(Profesion.ESTADO_CHOICES):
            return Response({'estado': ['Valor inválido.']}, status=status.HTTP_400_BAD_REQUEST)
        profesion.estado = nuevo_estado
        profesion.save(update_fields=['estado'])
        return Response(ProfesionSerializer(profesion).data)

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
