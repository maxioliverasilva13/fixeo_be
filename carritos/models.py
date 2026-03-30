from django.db import models
from usuario.models import Usuario
from empresas.models import Empresa, Producto
from fixeo_project.models import BaseModel

CURRENCY_CHOICES = [
    ('ARS', 'Peso Argentino'),
    ('BRL', 'Real Brasileño'),
    ('CLP', 'Peso Chileno'),
    ('COP', 'Peso Colombiano'),
    ('MXN', 'Peso Mexicano'),
    ('PEN', 'Sol Peruano'),
    ('UYU', 'Peso Uruguayo'),
    ('BOB', 'Boliviano'),
    ('PYG', 'Guaraní Paraguayo'),
    ('VES', 'Bolívar Venezolano'),
    ('CRC', 'Colón Costarricense'),
    ('DOP', 'Peso Dominicano'),
    ('GTQ', 'Quetzal Guatemalteco'),
    ('HNL', 'Lempira Hondureño'),
    ('NIO', 'Córdoba Nicaragüense'),
    ('PAB', 'Balboa Panameño'),
    ('USD', 'Dólar Estadounidense'),
]

class Carrito(BaseModel):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='carritos')
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='carritos')
    activo = models.BooleanField(default=True)

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
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'carrito_item'
        verbose_name = 'Item de Carrito'
        verbose_name_plural = 'Items de Carrito'
        unique_together = ['carrito', 'producto']

    def __str__(self):
        return f"{self.producto.nombre} x{self.cantidad}"

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
    pago_status = models.CharField(max_length=20, blank=True, default='', help_text='Estado del pago MP')
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

    class Meta:
        db_table = 'orden_item'
        verbose_name = 'Item de Orden'
        verbose_name_plural = 'Items de Orden'

    def __str__(self):
        return f"{self.producto.nombre} x{self.cantidad}"
