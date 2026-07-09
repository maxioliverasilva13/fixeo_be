from django.db import models
from usuario.models import Usuario
from fixeo_project.models import BaseModel


class Plan(BaseModel):
    nombre = models.CharField(max_length=200, default='Plan Básico')
    descripcion = models.TextField(blank=True, default='')
    precio = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cantidad_personas = models.IntegerField(default=1)
    duracion = models.DurationField()
    cantidad_jobs = models.IntegerField(default=5)          # <-- campo nuevo
    google_play_id = models.CharField(max_length=200, blank=True, null=True)
    appstore_id = models.CharField(max_length=200, blank=True, null=True)
    caracteristicas = models.JSONField(default=list)
    activo = models.BooleanField(default=True)
    tiene_landing_page = models.BooleanField(
        default=False,
        help_text='Si es True, las empresas con este plan pueden tener landing page pública.',
    )

    class Meta:
        db_table = 'plan'
        verbose_name = 'Plan'
        verbose_name_plural = 'Planes'
        indexes = [
            models.Index(fields=['precio', 'cantidad_jobs'], name='idx_plan_rank'),
        ]

    def __str__(self):
        return f"Plan {self.nombre}"


class SubscripcionSource(models.TextChoices):
    MANUAL = 'manual', 'Manual'
    GOOGLE_PLAY = 'google_play', 'Google Play'
    APP_STORE = 'app_store', 'App Store'


class SubscripcionStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    TRIALING = 'trialing', 'Trialing'
    CANCELED = 'canceled', 'Canceled'
    EXPIRED = 'expired', 'Expired'
    PAST_DUE = 'past_due', 'Past due'
    PAUSED = 'paused', 'Paused'
    REFUNDED = 'refunded', 'Refunded'


class Subscripcion(BaseModel):
    expiracion = models.DateTimeField()
    plan_id = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name='subscripciones')
    user_id = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='subscripciones')
    cancelada = models.BooleanField(default=False)
    jobs_restantes = models.IntegerField(default=0)
    source = models.CharField(
        max_length=20,
        choices=SubscripcionSource.choices,
        default=SubscripcionSource.MANUAL,
    )
    status = models.CharField(
        max_length=20,
        choices=SubscripcionStatus.choices,
        default=SubscripcionStatus.ACTIVE,
    )
    google_play_subscription_id = models.CharField(max_length=200, blank=True, null=True)
    google_play_purchase_token = models.TextField(blank=True, null=True)
    appstore_transaction_id = models.CharField(max_length=200, blank=True, null=True)
    appstore_original_transaction_id = models.CharField(max_length=200, blank=True, null=True, db_index=True)

    class Meta:
        db_table = 'subscripcion'
        verbose_name = 'Subscripción'
        verbose_name_plural = 'Subscripciones'
        indexes = [
            models.Index(
                fields=['user_id', 'cancelada', 'expiracion'],
                name='idx_sub_user_active',
            ),
        ]

    def __str__(self):
        return f"Subscripción {self.user_id} - {self.plan_id}"