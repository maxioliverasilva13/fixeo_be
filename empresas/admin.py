from django.contrib import admin
from .models import Empresa, Horarios, Servicios


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'ubicacion', 'admin_id', 'unipersonal', 'created_at')
    search_fields = ('nombre', 'descripcion')
    list_filter = ('created_at', 'unipersonal')


@admin.register(Horarios)
class HorariosAdmin(admin.ModelAdmin):
    list_display = ('empresa', 'dia_semana', 'hora_inicio', 'hora_fin', 'enabled')
    list_filter = ('dia_semana', 'enabled')
    search_fields = ('empresa__nombre',)


@admin.register(Servicios)
class ServiciosAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'empresa', 'precio_base')
    search_fields = ('nombre', 'descripcion', 'empresa__nombre')

