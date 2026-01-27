from django.contrib import admin
from .models import UsuarioLocalizacion


@admin.register(UsuarioLocalizacion)
class UsuarioLocalizacionAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'localizacion')
    search_fields = ('usuario__correo', 'localizacion__ubicacion')
