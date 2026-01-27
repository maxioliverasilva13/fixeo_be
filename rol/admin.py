from django.contrib import admin
from .models import Rol


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)
