from django.db import models
from django.conf import settings
from fixeo_project.models import BaseModel


class MercadoPagoCustomer(BaseModel):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='mp_customer'
    )
    mp_customer_id = models.CharField(max_length=255, unique=True)

    class Meta:
        db_table = 'mercadopago_customer'
        verbose_name = 'Customer MercadoPago'
        verbose_name_plural = 'Customers MercadoPago'

    def __str__(self):
        return f"MP Customer {self.mp_customer_id} - {self.usuario.correo}"


class Tarjeta(BaseModel):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='tarjetas'
    )
    mp_card_id = models.CharField(max_length=255)
    last_four = models.CharField(max_length=4)
    brand = models.CharField(max_length=50, blank=True, default='')
    expiration_month = models.IntegerField()
    expiration_year = models.IntegerField()
    payment_method_id = models.CharField(max_length=50, blank=True, default='')
    payment_type = models.CharField(max_length=30, blank=True, default='credit_card')
    issuer_id = models.CharField(max_length=50, blank=True, default='')

    class Meta:
        db_table = 'tarjeta'
        verbose_name = 'Tarjeta'
        verbose_name_plural = 'Tarjetas'
        unique_together = ['usuario', 'mp_card_id']

    def __str__(self):
        return f"**** {self.last_four} ({self.brand}) - {self.usuario.correo}"


class Pago(BaseModel):
    TIPO_CHOICES = [
        ('orden', 'Orden de productos'),
        ('trabajo', 'Trabajo/Servicio'),
    ]

    STATUS_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('aprobado', 'Aprobado'),
        ('rechazado', 'Rechazado'),
        ('en_proceso', 'En proceso'),
        ('devuelto', 'Devuelto'),
        ('cancelado', 'Cancelado'),
        ('liberado', 'Liberado'),
    ]

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    orden = models.ForeignKey(
        'carritos.Orden', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='pagos'
    )
    trabajo = models.ForeignKey(
        'trabajos.Trabajo', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='pagos'
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='pagos'
    )

    monto = models.DecimalField(max_digits=10, decimal_places=2)
    comision_plataforma = models.DecimalField(max_digits=10, decimal_places=2)
    monto_vendedor = models.DecimalField(max_digits=10, decimal_places=2)

    mp_preference_id = models.CharField(max_length=255, blank=True, default='')
    mp_order_id = models.CharField(max_length=255, blank=True, default='')
    mp_payment_id = models.CharField(max_length=255, blank=True, default='')
    mp_status = models.CharField(max_length=50, blank=True, default='')
    mp_status_detail = models.CharField(max_length=100, blank=True, default='')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendiente')
    liberado_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'pago'
        verbose_name = 'Pago'
        verbose_name_plural = 'Pagos'
        ordering = ['-created_at']

    def __str__(self):
        return f"Pago #{self.id} - {self.tipo} - {self.status} - ${self.monto}"

    @property
    def entidad_id(self):
        if self.tipo == 'orden' and self.orden:
            return self.orden.id
        if self.tipo == 'trabajo' and self.trabajo:
            return self.trabajo.id
        return None
