from django.contrib import admin
from .models import Disponibilidad


@admin.register(Disponibilidad)
class DisponibilidadAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'fecha_inicio', 'fecha_fin', 'tipo', 'origen')
    list_filter = ('tipo', 'origen', 'fecha_inicio')
    search_fields = ('usuario__correo', 'usuario__nombre', 'usuario__apellido')
    date_hierarchy = 'fecha_inicio'
