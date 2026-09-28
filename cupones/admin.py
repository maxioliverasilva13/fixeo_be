from django.contrib import admin

from .models import Cupon


@admin.register(Cupon)
class CuponAdmin(admin.ModelAdmin):
    list_display = (
        'codigo', 'empresa', 'cliente', 'tipo_descuento', 'valor',
        'estado', 'fecha_expiracion', 'fecha_uso', 'created_at',
    )
    list_filter = ('tipo_descuento',)
    search_fields = ('codigo', 'empresa__nombre', 'cliente__nombre', 'cliente__apellido')
