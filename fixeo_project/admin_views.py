"""
Views para el panel de estadísticas global (admin dashboard).
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from fixeo_project.estadisticas import estadisticas_globales


class AdminEstadisticasView(APIView):
    """
    GET /api/admin/estadisticas/
    Devuelve todas las estadísticas del sistema para el panel de admin.
    Query params opcionales: ?year=YYYY&month=MM
    Solo accesible para superadmins (is_staff=True).
    """
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        data = estadisticas_globales(request)
        return Response(data)
