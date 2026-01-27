from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import LocalizacionViewSet

router = DefaultRouter()
router.register(r'', LocalizacionViewSet, basename='localizacion')

urlpatterns = [
    path('', include(router.urls)),
]
