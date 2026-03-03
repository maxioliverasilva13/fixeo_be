from django.urls import path
from .views import (
    PlanListView,
    PlanDetailView,
    SubscripcionCreateView,
    MiSubscripcionActivaView,
    CancelarSubscripcionView,
    AdminSubscripcionListView,
)

planes_urlpatterns = [
    path('', PlanListView.as_view(), name='plan-list'),
    path('<int:pk>/', PlanDetailView.as_view(), name='plan-detail'),
]

suscripciones_urlpatterns = [
    path('', SubscripcionCreateView.as_view(), name='subscripcion-create'),
    path('mi-plan/', MiSubscripcionActivaView.as_view(), name='mi-subscripcion'),
    path('<int:pk>/cancelar/', CancelarSubscripcionView.as_view(), name='subscripcion-cancelar'),
    path('admin/', AdminSubscripcionListView.as_view(), name='admin-subscripcion-list'),
]

urlpatterns = planes_urlpatterns 