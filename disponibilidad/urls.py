from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DisponibilidadViewSet, dias_disponibles_mes, horas_disponibles_dia

router = DefaultRouter()
router.register(r'', DisponibilidadViewSet, basename='disponibilidad')

urlpatterns = [
    path('dias-disponibles-mes/', dias_disponibles_mes, name='dias-disponibles-mes'),
    path('horas-disponibles-dia/', horas_disponibles_dia, name='horas-disponibles-dia'),
    path('', include(router.urls)),

]
