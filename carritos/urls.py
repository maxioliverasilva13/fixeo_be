from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CarritoViewSet, OrdenViewSet

router_carritos = DefaultRouter()
router_carritos.register(r'', CarritoViewSet, basename='carrito')

router_ordenes = DefaultRouter()
router_ordenes.register(r'', OrdenViewSet, basename='orden')

urlpatterns = [
    path('carritos/', include(router_carritos.urls)),
    path('ordenes/', include(router_ordenes.urls)),
]
