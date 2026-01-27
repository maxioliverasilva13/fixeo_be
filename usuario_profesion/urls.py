from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UsuarioProfesionViewSet

router = DefaultRouter()
router.register(r'', UsuarioProfesionViewSet, basename='usuario-profesion')

urlpatterns = [
    path('', include(router.urls)),
]
