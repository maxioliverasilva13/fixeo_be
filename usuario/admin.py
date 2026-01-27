from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(BaseUserAdmin):
    list_display = ('correo', 'nombre', 'apellido', 'telefono', 'rol', 'is_owner_empresa', 'is_staff')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'is_owner_empresa', 'rol')
    fieldsets = (
        (None, {'fields': ('correo', 'password')}),
        ('Información Personal', {'fields': ('nombre', 'apellido', 'telefono', 'foto_url', 'rol')}),
        ('Trabajo', {'fields': ('trabajo_domicilio', 'trabajo_local')}),
        ('Permisos', {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_owner_empresa', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('correo', 'nombre', 'apellido', 'telefono', 'foto_url', 'rol', 'password1', 'password2'),
        }),
    )
    search_fields = ('correo', 'nombre', 'apellido')
    ordering = ('correo',)
