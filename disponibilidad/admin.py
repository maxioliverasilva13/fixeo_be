from django.contrib import admin
from .models import Disponibilidad


@admin.register(Disponibilidad)
class DisponibilidadAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'fecha_yyyy_mm_dd', 'hora_inicio', 'hora_fin')
    list_filter = ('fecha_yyyy_mm_dd',)
    search_fields = ('usuario__correo',)
