from django.contrib import admin
from .models import Empresa, Horarios, CategoriaProducto, Producto, ProductoDia, ProductoVariante


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = (
        'nombre', 'ubicacion', 'admin_id', 'unipersonal',
        'vende_productos', 'vende_servicios', 'vende_menu_diario', 'tiene_landing_page', 'created_at',
    )
    search_fields = ('nombre', 'descripcion')
    list_filter = (
        'created_at', 'unipersonal', 'vende_productos', 'vende_servicios',
        'vende_menu_diario', 'tiene_landing_page',
    )


@admin.register(CategoriaProducto)
class CategoriaProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'empresa', 'created_at')
    search_fields = ('nombre', 'descripcion', 'empresa__nombre')
    list_filter = ('created_at', 'empresa')


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'empresa', 'categoria', 'precio', 'codigo', 'agotado', 'es_menu_diario', 'created_at')
    search_fields = ('nombre', 'descripcion', 'codigo', 'empresa__nombre')
    list_filter = ('created_at', 'empresa', 'categoria', 'agotado', 'es_menu_diario')
    list_editable = ('agotado',)


@admin.register(ProductoDia)
class ProductoDiaAdmin(admin.ModelAdmin):
    list_display = ('producto', 'dia_semana', 'created_at')
    list_filter = ('dia_semana',)


@admin.register(ProductoVariante)
class ProductoVarianteAdmin(admin.ModelAdmin):
    list_display = ('producto', 'nombre', 'precio_extra', 'activo', 'orden')
    list_filter = ('activo',)

