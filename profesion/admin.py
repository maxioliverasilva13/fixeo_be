from django.contrib import admin
from .models import Profesion


@admin.register(Profesion)
class ProfesionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion', 'logo_svg_url')
    search_fields = ('nombre',)
