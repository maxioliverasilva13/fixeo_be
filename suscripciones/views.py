from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Plan, Subscripcion
from .serializers import (
    PlanSerializer,
    SubscripcionSerializer,
    SubscripcionCreateSerializer,
    UsuarioSubscripcionActivaSerializer,
)


class PlanListView(APIView):
    """
    GET /planes/
    Devuelve todos los planes activos. No requiere autenticación
    (la pantalla de listado de planes es pública).
    """

    def get(self, request):
        planes = Plan.objects.filter(activo=True).order_by('precio')
        serializer = PlanSerializer(planes, many=True)
        return Response(serializer.data)


class PlanDetailView(APIView):
    """
    GET /planes/<pk>/
    Detalle de un plan específico.
    """

    def get(self, request, pk):
        try:
            plan = Plan.objects.get(pk=pk, activo=True)
        except Plan.DoesNotExist:
            return Response({'detail': 'Plan no encontrado.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = PlanSerializer(plan)
        return Response(serializer.data)


class SubscripcionCreateView(APIView):
    """
    POST /suscripciones/
    Crea una suscripción para el usuario autenticado.
    Body: { "plan_id": <id>, "expiracion": "<datetime>" }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data.copy()
        data['user_id'] = request.user.pk

        serializer = SubscripcionCreateSerializer(data=data)
        if serializer.is_valid():
            subscripcion = serializer.save()
            return Response(
                SubscripcionSerializer(subscripcion).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MiSubscripcionActivaView(APIView):
    """
    GET /suscripciones/mi-plan/
    Devuelve la suscripción activa del usuario logueado:
    plan, jobs restantes y fecha de expiración.
    Si no tiene suscripción activa devuelve 404.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        subscripcion = (
            Subscripcion.objects
            .filter(
                user_id=request.user,
                cancelada=False,
                expiracion__gt=timezone.now(),
            )
            .select_related('plan_id')
            .order_by('-created_at')
            .first()
        )

        if not subscripcion:
            return Response(
                {'detail': 'No tenés una suscripción activa.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = UsuarioSubscripcionActivaSerializer(subscripcion)
        return Response(serializer.data)


class CancelarSubscripcionView(APIView):
    """
    PATCH /suscripciones/<pk>/cancelar/
    Cancela la suscripción del usuario autenticado.
    """
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            subscripcion = Subscripcion.objects.get(pk=pk, user_id=request.user)
        except Subscripcion.DoesNotExist:
            return Response({'detail': 'Suscripción no encontrada.'}, status=status.HTTP_404_NOT_FOUND)

        if subscripcion.cancelada:
            return Response({'detail': 'La suscripción ya está cancelada.'}, status=status.HTTP_400_BAD_REQUEST)

        subscripcion.cancelada = True
        subscripcion.save()
        return Response({'detail': 'Suscripción cancelada correctamente.'})


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

class AdminSubscripcionListView(APIView):
    """
    GET /admin/suscripciones/
    Lista todas las suscripciones (solo admins).
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        subs = Subscripcion.objects.select_related('plan_id', 'user_id').order_by('-created_at')
        serializer = SubscripcionSerializer(subs, many=True)
        return Response(serializer.data)