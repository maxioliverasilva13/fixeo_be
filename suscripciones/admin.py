from django.contrib import admin
from .models import Plan, Subscripcion, CampanaMarketing


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = (
        'nombre', 'precio', 'cantidad_personas', 'duracion',
        'google_play_id', 'appstore_id', 'activo', 'recomendado', 'created_at',
    )
    list_filter = ('activo', 'recomendado', 'created_at')
    search_fields = ('nombre', 'descripcion', 'google_play_id', 'appstore_id')


@admin.register(CampanaMarketing)
class CampanaMarketingAdmin(admin.ModelAdmin):
    list_display = (
        'nombre', 'plan', 'fecha_inicio', 'duracion', 'dias_gratis',
        'cupo_usuarios', 'activa',
    )
    list_filter = ('activa',)
    search_fields = ('nombre',)


@admin.register(Subscripcion)
class SubscripcionAdmin(admin.ModelAdmin):
    list_display = (
        'user_id', 'plan_id', 'source', 'status',
        'expiracion', 'cancelada', 'created_at',
    )
    list_filter = ('source', 'status', 'cancelada', 'created_at', 'expiracion')
    search_fields = (
        'user_id__correo',
        'google_play_subscription_id',
        'google_play_purchase_token',
        'appstore_transaction_id',
        'appstore_original_transaction_id',
    )

