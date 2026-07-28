from django.contrib import admin
from .models import Publicidad


@admin.register(Publicidad)
class PublicidadAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'tipo', 'dirigido_a', 'activa', 'fecha_expiracion', 'created_at')
    list_filter = ('tipo', 'dirigido_a', 'activa')
    search_fields = ('titulo', 'descripcion')
