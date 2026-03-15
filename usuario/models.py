from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from rol.models import Rol
import uuid
from django.utils import timezone
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector

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
    rango_mapa_km = models.DecimalField(max_digits=5, decimal_places=2, default=10.00, help_text='Radio de búsqueda en kilómetros')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_configured = models.BooleanField(default=False)
    rol = models.ForeignKey(Rol, on_delete=models.SET_NULL, null=True, blank=True, related_name='usuarios')
    rating = models.FloatField(default=0)
    cant_calif = models.IntegerField(default=0)

    auto_aprobacion_trabajos = models.BooleanField(default=False)

    objects = UsuarioManager()

    USERNAME_FIELD = 'correo'
    REQUIRED_FIELDS = ['nombre', 'apellido']

    class Meta:
        db_table = 'usuario'
        indexes = [
            GinIndex(
                SearchVector("nombre", "apellido"),
                name="usuario_search_idx"
            )
        ]
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return f"{self.nombre} {self.apellido} ({self.correo})"
    
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
