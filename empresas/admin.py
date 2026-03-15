from django.contrib import admin
from .models import Empresa, Horarios, CategoriaProducto, Producto


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'ubicacion', 'admin_id', 'unipersonal', 'vende_productos', 'vende_servicios', 'created_at')
    search_fields = ('nombre', 'descripcion')
    list_filter = ('created_at', 'unipersonal', 'vende_productos', 'vende_servicios')


@admin.register(CategoriaProducto)
class CategoriaProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'empresa', 'created_at')
    search_fields = ('nombre', 'descripcion', 'empresa__nombre')
    list_filter = ('created_at', 'empresa')


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'empresa', 'categoria', 'precio', 'codigo', 'agotado', 'created_at')
    search_fields = ('nombre', 'descripcion', 'codigo', 'empresa__nombre')
    list_filter = ('created_at', 'empresa', 'categoria', 'agotado')
    list_editable = ('agotado',)



