from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import WhatsAppMessageViewSet, whatsapp_webhook

router = DefaultRouter()
router.register(r'mensajes', WhatsAppMessageViewSet, basename='whatsapp-mensaje')

urlpatterns = [
    # Se registran ambas variantes (con y sin barra final) para no depender de un
    # redirect de Django ante un POST sin slash, que rompería el body del webhook.
    path('webhook', whatsapp_webhook, name='whatsapp-webhook-sin-slash'),
    path('webhook/', whatsapp_webhook, name='whatsapp-webhook'),
    path('', include(router.urls)),
]
