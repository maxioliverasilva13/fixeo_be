from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RolViewSet

router = DefaultRouter()
router.register(r'', RolViewSet, basename='rol')

urlpatterns = [
    path('', include(router.urls)),
]
