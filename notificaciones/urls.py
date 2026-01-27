from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DeviceTokenViewSet, NotificacionesViewSet, NotasViewSet

router = DefaultRouter()
router.register(r'device-tokens', DeviceTokenViewSet, basename='device-token')
router.register(r'', NotificacionesViewSet, basename='notificacion')
router.register(r'notas', NotasViewSet, basename='notas')

urlpatterns = [
    path('', include(router.urls)),
]

