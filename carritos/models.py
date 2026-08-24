from django.db import models
from usuario.models import Usuario
from empresas.models import Empresa, Producto
from fixeo_project.models import BaseModel
from localizacion.models import Localizacion
from enums.enums import CURRENCY_CHOICES

class Carrito(BaseModel):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='carritos')
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='carritos')
    activo = models.BooleanField(default=True)
    # Menú diario: todos los ítems del carrito son para esta fecha (un solo día).
    fecha_menu = models.DateField(
        null=True,
        blank=True,
        help_text='Fecha de entrega/consumo del menú diario. Un carrito = un solo día.',
    )

    class Meta:
        db_table = 'carrito'
        verbose_name = 'Carrito'
        verbose_name_plural = 'Carritos'
        constraints = [
            models.UniqueConstraint(
                fields=['usuario', 'empresa'],
                condition=models.Q(activo=True),
                name='unique_carrito_activo_por_usuario_empresa',
            ),
        ]

    def __str__(self):
        return f"Carrito de {self.usuario.nombre} - {self.empresa.nombre}"

    @property
    def total(self):
        return sum(item.subtotal for item in self.items.all())

    @property
    def cantidad_items(self):
        return sum(item.cantidad for item in self.items.all())


class CarritoItem(BaseModel):
    carrito = models.ForeignKey(Carrito, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    variante = models.ForeignKey(
        'empresas.ProductoVariante',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='carrito_items',
    )
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'carrito_item'
        verbose_name = 'Item de Carrito'
        verbose_name_plural = 'Items de Carrito'
        constraints = [
            models.UniqueConstraint(
                fields=['carrito', 'producto', 'variante'],
                name='unique_carrito_producto_variante',
                nulls_distinct=False,
            ),
        ]

    def __str__(self):
        label = self.producto.nombre
        if self.variante_id:
            label = f"{label} ({self.variante.nombre})"
        return f"{label} x{self.cantidad}"

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario


class Orden(BaseModel):
    STATUS_CHOICES = [
        ('en_proceso', 'En Proceso'),
        ('aceptada', 'Aceptada'),
        ('entregada', 'Entregada/Retirada'),
        ('finalizada', 'Finalizada'),
        ('cancelada', 'Cancelada'),
    ]

    METODO_PAGO_CHOICES = [
        ('efectivo', 'Efectivo'),
        ('tarjeta', 'Tarjeta'),
        ('transferencia', 'Transferencia'),
        ('app', 'Pago en app'),
        ('mercadopago', 'MercadoPago'),
    ]

    TIPO_ENTREGA_CHOICES = [
        ('retiro', 'Retiro en local'),
        ('domicilio', 'Envío a domicilio'),
    ]

    numero_orden = models.CharField(max_length=50, unique=True, editable=False)
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='ordenes')
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='ordenes')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='en_proceso')
    metodo_pago = models.CharField(max_length=20, choices=METODO_PAGO_CHOICES)
    tipo_entrega = models.CharField(max_length=20, choices=TIPO_ENTREGA_CHOICES)
    localizacion_entrega = models.ForeignKey('localizacion.Localizacion', on_delete=models.SET_NULL, null=True, related_name='ordenes')
    total = models.DecimalField(max_digits=10, decimal_places=2)
    comision_plataforma = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notas = models.TextField(blank=True, default='')
    fecha_entrega = models.DateTimeField(null=True, blank=True)
    motivo_cancelacion = models.TextField(blank=True, default='')
    pago_status = models.CharField(
        max_length=20,
        blank=True,
        default='',
        help_text='MP: aprobado/liberado/… | Manual (efectivo/transferencia): pendiente/pagado/pago_en_domicilio',
    )
    comprobante_pago_url = models.URLField(
        max_length=500,
        blank=True,
        default='',
        help_text='Foto/comprobante opcional al marcar el pago (transferencia/efectivo).',
    )
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = 'orden'
        verbose_name = 'Orden'
        verbose_name_plural = 'Órdenes'
        ordering = ['-created_at']

    def __str__(self):
        return f"Orden {self.numero_orden} - {self.usuario.nombre}"

    def save(self, *args, **kwargs):
        if not self.numero_orden:
            import uuid
            self.numero_orden = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)


class OrdenItem(BaseModel):
    orden = models.ForeignKey(Orden, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    variante_nombre = models.CharField(max_length=200, blank=True, default='')
    variante_precio_extra = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        db_table = 'orden_item'
        verbose_name = 'Item de Orden'
        verbose_name_plural = 'Items de Orden'

    def __str__(self):
        label = self.producto.nombre
        if self.variante_nombre:
            label = f"{label} ({self.variante_nombre})"
        return f"{label} x{self.cantidad}"
