from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PublicidadAdminViewSet, PublicidadActivasViewSet

router = DefaultRouter()
router.register(r'admin', PublicidadAdminViewSet, basename='publicidad-admin')
router.register(r'activas', PublicidadActivasViewSet, basename='publicidad-activa')

urlpatterns = [
    path('', include(router.urls)),
]
