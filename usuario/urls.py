from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UsuarioViewSet
from .views_zonas import ZonaNoTrabajoViewSet

router = DefaultRouter()
router.register(r'', UsuarioViewSet, basename='usuario')

zonas_router = DefaultRouter()
zonas_router.register(r'', ZonaNoTrabajoViewSet, basename='zona-no-trabajo')

urlpatterns = [
    path('zonas-no-trabajo/', include(zonas_router.urls)),
    path('', include(router.urls)),
]
