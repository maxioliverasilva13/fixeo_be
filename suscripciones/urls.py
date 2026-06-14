from .views import (
    PlanListView,
    PlanDetailView,
    SubscripcionCreateView,
    MiSubscripcionActivaView,
    CancelarSubscripcionView,
    AdminSubscripcionListView,
    AdminExtenderSubscripcionView,  
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
    path('admin/extender/', AdminExtenderSubscripcionView.as_view(), name='admin-extender-subscripcion'),  # ← nuevo

    path('google-play/subscribe/', GooglePlaySubscribeView.as_view(), name='google-play-subscribe'),
    path('google-play/cancel/', GooglePlayCancelView.as_view(), name='google-play-cancel'),
    path('google-play/webhook/', GooglePlayWebhookView.as_view(), name='google-play-webhook'),

    path('app-store/subscribe/', AppStoreSubscribeView.as_view(), name='app-store-subscribe'),
    path('app-store/cancel/', AppStoreCancelView.as_view(), name='app-store-cancel'),
    path('app-store/webhook/', AppStoreWebhookView.as_view(), name='app-store-webhook'),
]