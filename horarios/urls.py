from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import HorariosViewSet

router = DefaultRouter()
router.register(r'', HorariosViewSet, basename='horarios')

urlpatterns = [
    path('', include(router.urls)),
]
