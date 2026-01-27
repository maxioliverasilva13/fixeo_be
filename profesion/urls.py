from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProfesionViewSet

router = DefaultRouter()
router.register(r'', ProfesionViewSet, basename='profesion')

urlpatterns = [
    path('', include(router.urls)),
]
