import secrets
import string

from django.conf import settings
from django.db import models
from django.utils import timezone

from fixeo_project.models import BaseModel

CODIGO_ALPHABET = string.ascii_uppercase + string.digits
CODIGO_LENGTH = 8


def _generar_codigo() -> str:
    return ''.join(secrets.choice(CODIGO_ALPHABET) for _ in range(CODIGO_LENGTH))


class Cupon(BaseModel):
    """Cupón de descuento único para un cliente puntual de una empresa, canjeable
    en cualquier compra/reserva de esa empresa (carrito de productos, menú diario
    o reserva de servicios)."""

    class TipoDescuento(models.TextChoices):
        PORCENTAJE = 'porcentaje', 'Porcentaje'
        MONTO_FIJO = 'monto_fijo', 'Monto fijo'

    codigo = models.CharField(max_length=20, unique=True, editable=False)
    empresa = models.ForeignKey(
        'empresas.Empresa', on_delete=models.CASCADE, related_name='cupones',
    )
    cliente = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cupones_recibidos',
    )
    tipo_descuento = models.CharField(max_length=20, choices=TipoDescuento.choices)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_expiracion = models.DateTimeField(null=True, blank=True)
    fecha_uso = models.DateTimeField(null=True, blank=True)
    orden = models.ForeignKey(
        'carritos.Orden', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cupones_usados',
    )
    trabajo = models.ForeignKey(
        'trabajos.Trabajo', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cupones_usados',
    )

    class Meta:
        db_table = 'cupon'
        verbose_name = 'Cupón'
        verbose_name_plural = 'Cupones'
        indexes = [
            models.Index(fields=['codigo'], name='cupon_codigo_idx'),
            models.Index(fields=['empresa', 'cliente'], name='cupon_empresa_cliente_idx'),
        ]

    def save(self, *args, **kwargs):
        if not self.codigo:
            codigo = _generar_codigo()
            while Cupon.all_objects.filter(codigo=codigo).exists():
                codigo = _generar_codigo()
            self.codigo = codigo
        super().save(*args, **kwargs)

    @property
    def estado(self) -> str:
        if self.fecha_uso:
            return 'usado'
        if self.fecha_expiracion and self.fecha_expiracion < timezone.now():
            return 'expirado'
        return 'activo'

    def marcar_usado(self, *, orden=None, trabajo=None):
        self.fecha_uso = timezone.now()
        if orden is not None:
            self.orden = orden
        if trabajo is not None:
            self.trabajo = trabajo
        self.save(update_fields=['fecha_uso', 'orden', 'trabajo', 'updated_at'])

    def __str__(self):
        return f'Cupón {self.codigo} (empresa {self.empresa_id} → cliente {self.cliente_id})'
