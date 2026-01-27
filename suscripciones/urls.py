from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PlanViewSet, SubscripcionViewSet

router = DefaultRouter()
router.register(r'planes', PlanViewSet, basename='plan')
router.register(r'', SubscripcionViewSet, basename='subscripcion')

urlpatterns = [
    path('', include(router.urls)),
]

