from django.contrib import admin
from .models import DeviceToken, Notificaciones, Notas


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ('device_name', 'usuario', 'enabled', 'created_at')
    list_filter = ('enabled', 'created_at')
    search_fields = ('device_name', 'device_token', 'usuario__correo')


@admin.register(Notificaciones)
class NotificacionesAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'usuario', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('titulo', 'descripcion', 'usuario__correo')


@admin.register(Notas)
class NotasAdmin(admin.ModelAdmin):
    list_display = ('estado', 'fecha_siempre_en_utc', 'created_at')
    list_filter = ('estado', 'created_at')

