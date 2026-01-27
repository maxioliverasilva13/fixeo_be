"""
URL configuration for fixeo_project project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/usuarios/', include('usuario.urls')),
    path('api/roles/', include('rol.urls')),
    path('api/profesiones/', include('profesion.urls')),
    path('api/disponibilidades/', include('disponibilidad.urls')),
    path('api/usuario-profesiones/', include('usuario_profesion.urls')),
    path('api/usuario-localizaciones/', include('usuario_localizacion.urls')),
    path('api/localizaciones/', include('localizacion.urls')),
    path('api/empresas/', include('empresas.urls')),
    path('api/trabajos/', include('trabajos.urls')),
    path('api/mensajeria/', include('mensajeria.urls')),
    path('api/notificaciones/', include('notificaciones.urls')),
    path('api/suscripciones/', include('suscripciones.urls')),
    path('api/recursos/', include('recursos.urls')),
    path('api/servicios/', include('servicios.urls')),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

