from django.conf import settings
from django.db import models

from fixeo_project.models import BaseModel


class UsuarioBlock(BaseModel):
    """Usuario A bloquea a usuario B (feed/chat se ocultan de inmediato)."""

    blocker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='blocks_made',
    )
    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='blocks_received',
    )
    reason = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        db_table = 'moderacion_usuario_block'
        verbose_name = 'Bloqueo de usuario'
        verbose_name_plural = 'Bloqueos de usuario'
        constraints = [
            models.UniqueConstraint(
                fields=['blocker', 'blocked'],
                name='uniq_usuario_block_pair',
            ),
        ]

    def __str__(self):
        return f'{self.blocker_id} bloqueó a {self.blocked_id}'


class ContentReport(BaseModel):
    class ContentType(models.TextChoices):
        MESSAGE = 'message', 'Mensaje'
        CHAT = 'chat', 'Chat'
        PROFILE = 'profile', 'Perfil'
        RATING = 'rating', 'Calificación'
        OTHER = 'other', 'Otro'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        REVIEWED = 'reviewed', 'En revisión'
        ACTIONED = 'actioned', 'Acción tomada'
        DISMISSED = 'dismissed', 'Descartado'

    class Reason(models.TextChoices):
        SPAM = 'spam', 'Spam'
        HARASSMENT = 'harassment', 'Acoso o abuso'
        HATE = 'hate', 'Discurso de odio'
        SEXUAL = 'sexual', 'Contenido sexual'
        SCAM = 'scam', 'Estafa o fraude'
        OTHER = 'other', 'Otro'

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reports_made',
    )
    reported_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reports_received',
        null=True,
        blank=True,
    )
    content_type = models.CharField(max_length=20, choices=ContentType.choices)
    content_id = models.PositiveIntegerField(null=True, blank=True)
    reason = models.CharField(max_length=30, choices=Reason.choices, default=Reason.OTHER)
    details = models.TextField(blank=True, default='')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    admin_notes = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'moderacion_content_report'
        verbose_name = 'Reporte de contenido'
        verbose_name_plural = 'Reportes de contenido'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['reported_user', '-created_at']),
        ]

    def __str__(self):
        return f'Reporte #{self.id} ({self.content_type}/{self.content_id})'
