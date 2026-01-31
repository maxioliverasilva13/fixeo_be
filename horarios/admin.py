from django.contrib import admin
from empresas.models import Horarios


@admin.register(Horarios)
class HorariosAdmin(admin.ModelAdmin):
    list_display = ('empresa', 'dia_semana', 'hora_inicio', 'hora_fin', 'enabled')
    list_filter = ('enabled', 'dia_semana')
    search_fields = ('empresa__nombre',)
