from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    EmpresaViewSet,
    HorariosViewSet, ServiciosViewSet
)

router = DefaultRouter()
router.register(r'', EmpresaViewSet, basename='empresa')
router.register(r'horarios', HorariosViewSet, basename='horarios')
router.register(r'servicios', ServiciosViewSet, basename='servicios')

urlpatterns = [
    path('', include(router.urls)),
]

