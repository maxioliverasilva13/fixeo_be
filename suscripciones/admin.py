from django.contrib import admin
from .models import Plan, Subscripcion


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'precio', 'cantidad_personas', 'duracion', 'activo', 'created_at')
    list_filter = ('activo', 'created_at')
    search_fields = ('nombre', 'descripcion', 'google_play_id', 'appstore_id')


@admin.register(Subscripcion)
class SubscripcionAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'plan_id', 'expiracion', 'cancelada', 'created_at')
    list_filter = ('cancelada', 'created_at', 'expiracion')
    search_fields = ('user_id__correo',)

