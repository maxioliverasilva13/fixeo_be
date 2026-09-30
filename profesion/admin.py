from django.contrib import admin
from .models import Profesion


@admin.register(Profesion)
class ProfesionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'estado', 'descripcion', 'logo_svg_url')
    list_filter = ('estado',)
    search_fields = ('nombre',)
