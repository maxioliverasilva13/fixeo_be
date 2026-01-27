from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ChatViewSet, MensajesViewSet, RecursoViewSet

router = DefaultRouter()
router.register(r'chats', ChatViewSet, basename='chat')
router.register(r'mensajes', MensajesViewSet, basename='mensajes')
router.register(r'recursos', RecursoViewSet, basename='recurso')

urlpatterns = [
    path('', include(router.urls)),
]

