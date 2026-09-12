from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TrabajoViewSet,
    CalificacionViewSet,
    confirmar_trabajo_por_token,
    rechazar_trabajo_por_token,
)
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
    # Confirmar/rechazar por token (link del template de WhatsApp al profesional,
    # sin autenticación: el token UUID es el secreto).
    path('confirmar/<uuid:token>/', confirmar_trabajo_por_token, name='trabajo-confirmar-token'),
    path('rechazar/<uuid:token>/', rechazar_trabajo_por_token, name='trabajo-rechazar-token'),
    path('urgente/', include(router_urgente.urls)),
    path('', include(router.urls)),
]

