from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EmpresaViewSet, CategoriaProductoViewSet, ProductoViewSet, AdminEmpresaViewSet, EmpresaPublicLandingView

router = DefaultRouter()
router.register(r'', EmpresaViewSet, basename='empresa')

router_categorias = DefaultRouter()
router_categorias.register(r'', CategoriaProductoViewSet, basename='categoria-producto')

router_productos = DefaultRouter()
router_productos.register(r'', ProductoViewSet, basename='producto')

router_admin_empresas = DefaultRouter()
router_admin_empresas.register(r'', AdminEmpresaViewSet, basename='admin-empresa')

urlpatterns = [
    path('public/<str:subdomain>/', EmpresaPublicLandingView.as_view(), name='empresa-public-landing'),
    path('categorias/', include(router_categorias.urls)),
    path('productos/', include(router_productos.urls)),
    path('admin/', include(router_admin_empresas.urls)),
    path('', include(router.urls)),
]
