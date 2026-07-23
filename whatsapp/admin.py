from django.contrib import admin

from .models import WhatsAppMessage


@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display = ('wa_id', 'usuario', 'direccion', 'tipo', 'estado', 'created_at')
    list_filter = ('direccion', 'tipo', 'estado')
    search_fields = ('wa_id', 'wa_message_id', 'texto')
    readonly_fields = ('created_at', 'updated_at')
