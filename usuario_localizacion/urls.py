from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UsuarioLocalizacionViewSet

router = DefaultRouter()
router.register(r'', UsuarioLocalizacionViewSet, basename='usuario-localizacion')

urlpatterns = [
    path('', include(router.urls)),
]
