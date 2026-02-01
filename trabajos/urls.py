from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TrabajoViewSet, CalificacionViewSet

router = DefaultRouter()
router.register(r'', TrabajoViewSet, basename='trabajo')

urlpatterns = [
    path('calificaciones/', CalificacionViewSet.as_view({'post': 'create'}), name='calificacion-create'),
    path('calificaciones/resumen/<int:usuario_id>/', CalificacionViewSet.as_view({'get': 'resumen'}), name='calificacion-resumen'),
    path('', include(router.urls)),
]

