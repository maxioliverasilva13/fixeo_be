from django.contrib import admin
from .models import Trabajo, Calificacion, Estados


@admin.register(Trabajo)
class TrabajoAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'usuario', 'status', 'precio_final', 'created_at')
    list_filter = ('status', 'created_at', 'cancelado_cliente')
    search_fields = ('titulo', 'descripcion', 'usuario__correo', 'categoria')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by', 'deleted_at', 'deleted_by')
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('titulo', 'descripcion', 'categoria', 'status')
        }),
        ('Detalles del Trabajo', {
            'fields': ('usuario', 'profesional', 'servicio', 'precio_final')
        }),
        ('Fechas', {
            'fields': ('fecha_inicio', 'fecha_fin')
        }),
        ('Estado', {
            'fields': ('cancelado_cliente', 'comentario_cliente')
        }),
        ('Auditoría', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Calificacion)
class CalificacionAdmin(admin.ModelAdmin):
    list_display = ('rating', 'user_cal_sender', 'user_cal_recibe', 'trabajo', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('comentario', 'user_cal_sender__correo', 'user_cal_recibe__correo')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')


@admin.register(Estados)
class EstadosAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'finalizador', 'created_at')
    list_filter = ('finalizador', 'nombre')
    search_fields = ('nombre',)
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'updated_by')

