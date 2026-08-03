from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ModeracionViewSet

router = DefaultRouter()
router.register(r'', ModeracionViewSet, basename='moderacion')

urlpatterns = [
    path('', include(router.urls)),
]
