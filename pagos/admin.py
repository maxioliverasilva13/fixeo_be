from django.contrib import admin
from .models import MercadoPagoCustomer, Pago, Tarjeta


@admin.register(MercadoPagoCustomer)
class MercadoPagoCustomerAdmin(admin.ModelAdmin):
    list_display = ['id', 'usuario', 'mp_customer_id', 'created_at']
    search_fields = ['mp_customer_id', 'usuario__correo']


@admin.register(Tarjeta)
class TarjetaAdmin(admin.ModelAdmin):
    list_display = ['id', 'usuario', 'last_four', 'brand', 'expiration_month', 'expiration_year', 'created_at']
    list_filter = ['brand']
    search_fields = ['usuario__correo', 'last_four']


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'tipo', 'usuario', 'monto', 'comision_plataforma',
        'monto_vendedor', 'status', 'mp_status', 'created_at',
    ]
    list_filter = ['tipo', 'status', 'mp_status']
    search_fields = ['mp_payment_id', 'mp_preference_id', 'usuario__correo']
    readonly_fields = [
        'mp_preference_id', 'mp_payment_id', 'mp_status',
        'mp_status_detail', 'liberado_at',
    ]
