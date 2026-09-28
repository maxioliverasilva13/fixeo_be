from django.db import models
from django.utils import timezone
from usuario.models import Usuario
from fixeo_project.models import BaseModel


class Plan(BaseModel):
    nombre = models.CharField(max_length=200, default='Plan Básico')
    descripcion = models.TextField(blank=True, default='')
    precio = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cantidad_personas = models.IntegerField(default=1)
    duracion = models.DurationField()
    google_play_id = models.CharField(max_length=200, blank=True, null=True)
    appstore_id = models.CharField(max_length=200, blank=True, null=True)
    caracteristicas = models.JSONField(default=list)
    activo = models.BooleanField(default=True)
    tiene_landing_page = models.BooleanField(
        default=False,
        help_text='Si es True, las empresas con este plan pueden tener landing page pública.',
    )
    recomendado = models.BooleanField(
        default=False,
        help_text='Se muestra preseleccionado y destacado como "Recomendado" en /planes.',
    )
    badge_mapa_url = models.URLField(
        max_length=500, blank=True, null=True,
        help_text=(
            'SVG o PNG (transparente) del pin de mapa para este plan: un agujero '
            'circular transparente en el centro es donde se compone la foto del usuario.'
        ),
    )
    user_badge_url = models.URLField(
        max_length=500, blank=True, null=True,
        help_text=(
            'SVG o PNG del ícono/insignia que se muestra sobre la foto del usuario '
            '(buscador, detalle de perfil desde el mapa, perfil propio) para este plan.'
        ),
    )
    color = models.CharField(
        max_length=7, blank=True, null=True,
        help_text='Color hex (ej. #F59E0B) usado en el badge/anillo del plan. Vacío = gris por defecto.',
    )
    slogan = models.CharField(
        max_length=40, blank=True, default='',
        help_text='Texto corto del badge del plan (ej. "Pro"). Vacío = usa el nombre del plan.',
    )
    cantidad_jobs = models.IntegerField(default=5)          # <-- campo nuevo

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


class CampanaMarketing(BaseModel):
    """Campaña temporal que habilita ofrecer un plan gratis (el elegido en
    `plan`), mostrando su precio real tachado, a nuevos registros."""
    nombre = models.CharField(max_length=200)
    plan = models.ForeignKey(
        Plan, on_delete=models.PROTECT, related_name='campanas',
        help_text='Plan que se regala mientras la campaña esté vigente.',
    )
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    duracion = models.DurationField(help_text='Tiempo que la campaña acepta nuevos registros gratis.')
    dias_gratis = models.PositiveIntegerField(help_text='Duración de la suscripción gratis otorgada.')
    mensaje_promocional = models.TextField(
        blank=True, default='',
        help_text='Texto libre que se muestra junto al plan en /planes mientras la campaña esté vigente.',
    )
    cupo_usuarios = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Cantidad máxima de usuarios para el mensaje "primeros X clientes". Vacío = sin límite.',
    )
    activa = models.BooleanField(default=True, help_text='Toggle manual del admin.')

    class Meta:
        db_table = 'campana_marketing'
        verbose_name = 'Campaña de marketing'
        verbose_name_plural = 'Campañas de marketing'

    def __str__(self):
        return f"Campaña {self.nombre}"

    def usuarios_inscriptos(self):
        return Subscripcion.objects.filter(campana=self).values('user_id').distinct().count()

    def esta_vigente(self):
        if not self.activa:
            return False
        if timezone.now() > self.fecha_inicio + self.duracion:
            return False
        if self.cupo_usuarios is not None and self.usuarios_inscriptos() >= self.cupo_usuarios:
            return False
        return True


class Subscripcion(BaseModel):
    expiracion = models.DateTimeField()
    plan_id = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name='subscripciones')
    user_id = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='subscripciones')
    campana = models.ForeignKey(
        CampanaMarketing, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='subscripciones',
    )
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