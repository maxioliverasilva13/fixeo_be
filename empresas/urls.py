from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    EmpresaViewSet,
    HorariosViewSet
)

router = DefaultRouter()
router.register(r'', EmpresaViewSet, basename='empresa')
router.register(r'horarios', HorariosViewSet, basename='horarios')

urlpatterns = [
    path('', include(router.urls)),
]

