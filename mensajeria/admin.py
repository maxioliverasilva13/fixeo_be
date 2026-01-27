from django.contrib import admin
from .models import Chat, Mensajes, Recurso


@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ('sender_id', 'received_id', 'created_at')
    search_fields = ('sender_id__correo', 'received_id__correo')


@admin.register(Mensajes)
class MensajesAdmin(admin.ModelAdmin):
    list_display = ('mensaje_id', 'sender_id', 'chat', 'created_at')
    search_fields = ('sender_id__correo',)


@admin.register(Recurso)
class RecursoAdmin(admin.ModelAdmin):
    list_display = ('url', 'mensaje', 'created_at')
    search_fields = ('url',)

