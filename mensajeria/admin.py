from django.contrib import admin
from .models import Chat, Mensajes, Recurso


@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender', 'receiver', 'trabajo', 'ultimo_mensaje_at', 'created_at')
    list_filter = ('created_at', 'ultimo_mensaje_at')
    search_fields = ('sender__correo', 'receiver__correo', 'sender__nombre', 'receiver__nombre')
    raw_id_fields = ('sender', 'receiver', 'trabajo')


@admin.register(Mensajes)
class MensajesAdmin(admin.ModelAdmin):
    list_display = ('mensaje_id', 'sender', 'chat', 'leido', 'created_at')
    list_filter = ('leido', 'created_at')
    search_fields = ('sender__correo', 'texto')
    raw_id_fields = ('sender', 'chat')


@admin.register(Recurso)
class RecursoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'tipo', 'url', 'mensaje', 'chat', 'created_at')
    list_filter = ('tipo', 'created_at')
    search_fields = ('nombre', 'url')
    raw_id_fields = ('mensaje', 'chat')

