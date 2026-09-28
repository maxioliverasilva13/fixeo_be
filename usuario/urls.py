from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UsuarioViewSet, AdminUsuarioViewSet,
    AdminBusquedaListView, AdminBusquedaDetalleView,
)
from .views_zonas import ZonaNoTrabajoViewSet

router = DefaultRouter()
router.register(r'', UsuarioViewSet, basename='usuario')

admin_router = DefaultRouter()
admin_router.register(r'', AdminUsuarioViewSet, basename='admin-usuario')

zonas_router = DefaultRouter()
zonas_router.register(r'', ZonaNoTrabajoViewSet, basename='zona-no-trabajo')

urlpatterns = [
    path('zonas-no-trabajo/', include(zonas_router.urls)),
    # Deben ir antes de admin/<pk>/ (admin_router con lookup r'[^/.]+') para no
    # ser interpretados como un pk de AdminUsuarioViewSet.
    path('admin/busquedas/detalle/', AdminBusquedaDetalleView.as_view()),
    path('admin/busquedas/', AdminBusquedaListView.as_view()),
    path('admin/', include(admin_router.urls)),
    path('', include(router.urls)),
]
