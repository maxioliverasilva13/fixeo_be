from django.db import models
from django.conf import settings
import uuid
from fixeo_project.models import BaseModel

class SurveyResponse(BaseModel):
    
    class Likelihood(models.TextChoices):
        DEFINITE = 'definite', 'Definitivamente'
        LIKELY   = 'likely',   'Probablemente'
        MAYBE    = 'maybe',    'Tal vez'
        NO       = 'no',       'No'

    class Role(models.TextChoices):
        USER = 'user', 'Usuario'
        PRO  = 'pro',  'Profesional'
        BOTH = 'both', 'Ambos'

    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name           = models.CharField(max_length=120, null=True, blank=True, verbose_name='Nombre')
    email          = models.EmailField(max_length=255, null=True, blank=True, verbose_name='Correo electrónico')
    likelihood     = models.CharField(max_length=20, choices=Likelihood.choices, verbose_name='Intención de uso')
    role           = models.CharField(max_length=20, choices=Role.choices, verbose_name='Perfil')
    willing_to_pay = models.BooleanField(null=True, blank=True, verbose_name='Dispuesto a pagar')
    submitted_at   = models.DateTimeField(auto_now_add=True, verbose_name='Enviado en')
    source         = models.CharField(max_length=60, default='landing_page', verbose_name='Origen')
    ip_address     = models.GenericIPAddressField(protocol='both', null=True, blank=True, verbose_name='Dirección IP')
    user_agent     = models.TextField(null=True, blank=True, verbose_name='User Agent')

    class Meta(BaseModel.Meta):
        db_table    = 'survey_responses'
        verbose_name        = 'Respuesta de encuesta'
        verbose_name_plural = 'Respuestas de encuesta'
        indexes = [
            models.Index(fields=['email'],        name='idx_sr_email',        condition=models.Q(email__isnull=False)),
            models.Index(fields=['role'],          name='idx_sr_role'),
            models.Index(fields=['likelihood'],    name='idx_sr_likelihood'),
            models.Index(fields=['-submitted_at'], name='idx_sr_submitted_at'),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.role != self.Role.PRO and self.willing_to_pay is not None:
            raise ValidationError({'willing_to_pay': 'Solo aplica cuando el perfil es "pro".'})

    def __str__(self):
        return f"{self.name or 'Anónimo'} — {self.likelihood} ({self.submitted_at:%Y-%m-%d})"
