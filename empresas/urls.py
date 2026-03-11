from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EmpresaViewSet, CategoriaProductoViewSet, ProductoViewSet

router = DefaultRouter()
router.register(r'', EmpresaViewSet, basename='empresa')

router_categorias = DefaultRouter()
router_categorias.register(r'', CategoriaProductoViewSet, basename='categoria-producto')

router_productos = DefaultRouter()
router_productos.register(r'', ProductoViewSet, basename='producto')

urlpatterns = [
    path('categorias/', include(router_categorias.urls)),
    path('productos/', include(router_productos.urls)),
    path('', include(router.urls)),
]
