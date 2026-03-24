from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PagoViewSet, webhook_mercadopago

router = DefaultRouter()
router.register(r'', PagoViewSet, basename='pago')

urlpatterns = [
    path('webhook/', webhook_mercadopago, name='mp-webhook'),
    path('', include(router.urls)),
]
