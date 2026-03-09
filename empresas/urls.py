from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EmpresaViewSet, ProductoViewSet

router = DefaultRouter()

router.register(r'empresas', EmpresaViewSet, basename='empresa')
router.register(r'productos', ProductoViewSet, basename='producto')

urlpatterns = [
    path('', include(router.urls)),

]
