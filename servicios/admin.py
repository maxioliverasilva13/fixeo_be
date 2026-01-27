from django.contrib import admin
from .models import Servicio


@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    list_display = ['id', 'usuario', 'profesion', 'precio', 'divisa', 'tiempo', 'created_at']
    list_filter = ['divisa', 'created_at']
    search_fields = ['usuario__nombre', 'usuario__apellido', 'profesion__nombre']
    readonly_fields = ['created_at', 'updated_at']
