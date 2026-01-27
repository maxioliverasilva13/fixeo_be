from django.contrib import admin
from .models import Localizacion


@admin.register(Localizacion)
class LocalizacionAdmin(admin.ModelAdmin):
    list_display = ['id', 'ubicacion', 'city', 'country', 'latitud', 'longitud', 'created_at']
    list_filter = ['country', 'city', 'created_at']
    search_fields = ['ubicacion', 'address', 'city', 'country']
    readonly_fields = ['created_at', 'updated_at']
