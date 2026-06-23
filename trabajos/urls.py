from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TrabajoViewSet, CalificacionViewSet
from .views_urgente import TrabajoUrgenteViewSet

router = DefaultRouter()
router.register(r'', TrabajoViewSet, basename='trabajo')

router_urgente = DefaultRouter()
router_urgente.register(r'', TrabajoUrgenteViewSet, basename='trabajo-urgente')

urlpatterns = [
    path('calificaciones/', CalificacionViewSet.as_view({'post': 'create'}), name='calificacion-create'),
    path('calificaciones/resumen/<int:usuario_id>/', CalificacionViewSet.as_view({'get': 'resumen'}), name='calificacion-resumen'),
    path('calificaciones-cliente/<int:usuario_id>/', CalificacionViewSet.as_view({'get': 'listado_cliente'}), name='calificacion-cliente-list'),
    path('calificaciones-cliente/resumen/<int:usuario_id>/', CalificacionViewSet.as_view({'get': 'resumen_cliente'}), name='calificacion-cliente-resumen'),
    path('urgente/', include(router_urgente.urls)),
    path('', include(router.urls)),
]

