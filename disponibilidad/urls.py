from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DisponibilidadViewSet

router = DefaultRouter()
router.register(r'', DisponibilidadViewSet, basename='disponibilidad')

urlpatterns = [
    path('', include(router.urls)),
]
