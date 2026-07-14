from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from rol.models import Rol
import uuid
from django.utils import timezone
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector
from fixeo_project.models import BaseModel

class UsuarioManager(BaseUserManager):
    def create_user(self, correo, password=None, **extra_fields):
        if not correo:
            raise ValueError('El correo es obligatorio')
        correo = self.normalize_email(correo)
        user = self.model(correo=correo, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, correo, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(correo, password, **extra_fields)


class Usuario(AbstractBaseUser, PermissionsMixin):
    correo = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    defaultMessageReservation = models.CharField(max_length=1000, default='Gracias por reservar!. En breve nos pondremos en contacto contigo')
    apellido = models.CharField(max_length=100)
    telefono = models.CharField(max_length=20)
    nombre = models.CharField(max_length=100)
    foto_url = models.URLField(max_length=500, blank=True, null=True)
    rounded_foto_url = models.URLField(max_length=500, blank=True, null=True)
    trabajo_domicilio = models.BooleanField(default=False)
    trabajo_local = models.BooleanField(default=False)
    is_owner_empresa = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False, db_index=True, verbose_name='Eliminado')
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='Eliminado en')
    rango_mapa_km = models.DecimalField(max_digits=5, decimal_places=2, default=10.00, help_text='Radio de búsqueda en kilómetros')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_configured = models.BooleanField(default=False)
    rol = models.ForeignKey(Rol, on_delete=models.SET_NULL, null=True, blank=True, related_name='usuarios')
    rating = models.FloatField(default=0)
    cant_calif = models.IntegerField(default=0)
    rating_cliente = models.FloatField(default=0)
    cant_calif_cliente = models.IntegerField(default=0)
    token_ultima_actividad = models.DateTimeField(null=True, blank=True)

    auto_aprobacion_trabajos = models.BooleanField(default=False)
    recibir_notificaciones = models.BooleanField(
        default=True,
        help_text='Si es True, el usuario recibe push notifications.',
    )
    recibir_correos = models.BooleanField(
        default=True,
        help_text='Si es True, el usuario recibe emails de notificación.',
    )

    objects = UsuarioManager()

    USERNAME_FIELD = 'correo'
    REQUIRED_FIELDS = ['nombre', 'apellido']

    class Meta:
        db_table = 'usuario'
        indexes = [
            GinIndex(
                fields=["nombre"],
                name="usuario_nombre_trgm",
                opclasses=["gin_trgm_ops"]
            ),
            GinIndex(
                fields=["apellido"],
                name="usuario_apellido_trgm",
                opclasses=["gin_trgm_ops"]
            ),
            models.Index(
                fields=['is_owner_empresa', 'is_active'],
                name='idx_usuario_mapa_empresa',
            ),
        ]
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return f"{self.nombre} {self.apellido} ({self.correo})"


class ZonaNoTrabajo(BaseModel):
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name='zonas_no_trabajo',
    )
    nombre = models.CharField(max_length=100, blank=True, default='')
    latitud = models.DecimalField(max_digits=10, decimal_places=7)
    longitud = models.DecimalField(max_digits=10, decimal_places=7)
    radio_km = models.DecimalField(max_digits=5, decimal_places=2)
    activa = models.BooleanField(default=True)

    class Meta:
        db_table = 'zona_no_trabajo'
        verbose_name = 'Zona de no trabajo'
        verbose_name_plural = 'Zonas de no trabajo'
        indexes = [
            models.Index(fields=['usuario', 'activa'], name='idx_zona_no_trabajo_user'),
        ]

    def __str__(self):
        label = self.nombre or f'Zona {self.id}'
        return f'{label} ({self.usuario_id})'

    
class PasswordResetToken(models.Model):
    usuario   = models.ForeignKey('usuario.Usuario', on_delete=models.CASCADE, related_name='reset_tokens')
    token     = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    used      = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def is_valid(self):
        """Token válido por 1 hora y no utilizado."""
        return not self.used and (timezone.now() - self.created_at).seconds < 3600

    def __str__(self):
        return f"Reset token for {self.usuario.correo}"
