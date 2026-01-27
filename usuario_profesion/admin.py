from django.contrib import admin
from .models import UsuarioProfesion


@admin.register(UsuarioProfesion)
class UsuarioProfesionAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'profesion')
    search_fields = ('usuario__correo', 'profesion__nombre')
    list_filter = ('profesion',)
