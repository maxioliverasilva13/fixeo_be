from django.contrib import admin
from .models import Empresa, Horarios


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'ubicacion', 'admin_id', 'unipersonal', 'created_at')
    search_fields = ('nombre', 'descripcion')
    list_filter = ('created_at', 'unipersonal')
