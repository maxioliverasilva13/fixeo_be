from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProfesionViewSet, AdminProfesionViewSet

router = DefaultRouter()
router.register(r'', ProfesionViewSet, basename='profesion')

admin_router = DefaultRouter()
admin_router.register(r'', AdminProfesionViewSet, basename='admin-profesion')

urlpatterns = [
    path('admin/', include(admin_router.urls)),
    path('', include(router.urls)),
]
