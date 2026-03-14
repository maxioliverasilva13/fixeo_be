from django.contrib import admin
from .models import Servicio


@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    list_display = ['id', 'usuario', 'profesion', 'nombre', 'precio', 'divisa', 'tiempo', 'foto', 'created_at']
    list_filter = ['divisa', 'created_at']
    search_fields = ['usuario__nombre', 'usuario__apellido', 'profesion__nombre', 'nombre']
    readonly_fields = ['created_at', 'updated_at']
