from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CuponViewSet

router = DefaultRouter()
router.register(r'', CuponViewSet, basename='cupon')

urlpatterns = [
    path('', include(router.urls)),
]
