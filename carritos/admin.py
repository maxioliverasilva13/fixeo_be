from django.contrib import admin
from .models import Carrito, CarritoItem, Orden, OrdenItem


@admin.register(Carrito)
class CarritoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'empresa', 'activo', 'created_at')
    list_filter = ('activo', 'created_at', 'empresa')
    search_fields = ('usuario__nombre', 'usuario__apellido', 'empresa__nombre')


@admin.register(CarritoItem)
class CarritoItemAdmin(admin.ModelAdmin):
    list_display = ('carrito', 'producto', 'cantidad', 'precio_unitario', 'subtotal')
    search_fields = ('producto__nombre', 'carrito__usuario__nombre')


@admin.register(Orden)
class OrdenAdmin(admin.ModelAdmin):
    list_display = ('numero_orden', 'usuario', 'empresa', 'status', 'tipo_entrega', 'metodo_pago', 'total', 'created_at')
    list_filter = ('status', 'tipo_entrega', 'metodo_pago', 'created_at', 'empresa')
    search_fields = ('numero_orden', 'usuario__nombre', 'usuario__apellido', 'empresa__nombre')
    readonly_fields = ('numero_orden',)


@admin.register(OrdenItem)
class OrdenItemAdmin(admin.ModelAdmin):
    list_display = ('orden', 'producto', 'cantidad', 'precio_unitario', 'subtotal')
    search_fields = ('producto__nombre', 'orden__numero_orden')
