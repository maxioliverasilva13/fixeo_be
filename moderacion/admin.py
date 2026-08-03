from django.contrib import admin

from .models import ContentReport, UsuarioBlock


@admin.register(UsuarioBlock)
class UsuarioBlockAdmin(admin.ModelAdmin):
    list_display = ('id', 'blocker', 'blocked', 'reason', 'created_at')
    search_fields = ('blocker__correo', 'blocked__correo', 'blocker__nombre', 'blocked__nombre')
    raw_id_fields = ('blocker', 'blocked')


@admin.register(ContentReport)
class ContentReportAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'status', 'content_type', 'content_id',
        'reason', 'reporter', 'reported_user', 'created_at',
    )
    list_filter = ('status', 'content_type', 'reason')
    search_fields = ('details', 'reporter__correo', 'reported_user__correo')
    raw_id_fields = ('reporter', 'reported_user')
    readonly_fields = ('created_at', 'updated_at')
