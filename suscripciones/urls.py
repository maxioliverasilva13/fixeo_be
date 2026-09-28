from django.urls import path  # ← faltaba esto
from .views import (
    PlanListView,
    PlanDetailView,
    SubscripcionCreateView,
    MiSubscripcionActivaView,
    CancelarSubscripcionView,
    AdminSubscripcionListView,
    AdminExtenderSubscripcionView,
    AdminAsignarSubscripcionView,
    AdminCampanaListCreateView,
    AdminCampanaDetailView,
    AdminCampanaToggleView,
    AdminCampanaUsuariosView,
    AdminPlanListCreateView,
    AdminPlanDetailView,
    GooglePlaySubscribeView,
    GooglePlayCancelView,
    GooglePlayWebhookView,
    AppStoreSubscribeView,
    AppStoreCancelView,
    AppStoreWebhookView,
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
    path('admin/extender/', AdminExtenderSubscripcionView.as_view(), name='admin-extender-subscripcion'),
    path('admin/asignar/', AdminAsignarSubscripcionView.as_view(), name='admin-asignar-subscripcion'),
    path('admin/campanas/', AdminCampanaListCreateView.as_view(), name='admin-campana-list'),
    path('admin/campanas/<int:pk>/', AdminCampanaDetailView.as_view(), name='admin-campana-detail'),
    path('admin/campanas/<int:pk>/toggle/', AdminCampanaToggleView.as_view(), name='admin-campana-toggle'),
    path('admin/campanas/<int:pk>/usuarios/', AdminCampanaUsuariosView.as_view(), name='admin-campana-usuarios'),
    path('admin/planes/', AdminPlanListCreateView.as_view(), name='admin-plan-list'),
    path('admin/planes/<int:pk>/', AdminPlanDetailView.as_view(), name='admin-plan-detail'),

    path('google-play/subscribe/', GooglePlaySubscribeView.as_view(), name='google-play-subscribe'),
    path('google-play/cancel/', GooglePlayCancelView.as_view(), name='google-play-cancel'),
    path('google-play/webhook/', GooglePlayWebhookView.as_view(), name='google-play-webhook'),

    path('app-store/subscribe/', AppStoreSubscribeView.as_view(), name='app-store-subscribe'),
    path('app-store/cancel/', AppStoreCancelView.as_view(), name='app-store-cancel'),
    path('app-store/webhook/', AppStoreWebhookView.as_view(), name='app-store-webhook'),
]

urlpatterns = planes_urlpatterns