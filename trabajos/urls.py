from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TrabajoViewSet, CalificacionViewSet, EstadosViewSet

router = DefaultRouter()
router.register(r'', TrabajoViewSet, basename='trabajo')
router.register(r'calificaciones', CalificacionViewSet, basename='calificacion')
router.register(r'estados', EstadosViewSet, basename='estados')

urlpatterns = [
    path('', include(router.urls)),
]

