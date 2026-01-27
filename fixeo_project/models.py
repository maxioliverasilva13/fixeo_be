from django.db import models
from django.conf import settings
from django.utils import timezone


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

    def all_with_deleted(self):
        return super().get_queryset()

    def deleted_only(self):
        return super().get_queryset().filter(is_deleted=True)


class BaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Creado en', db_index=True)
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Actualizado en')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_created',
        verbose_name='Creado por'
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_updated',
        verbose_name='Actualizado por'
    )
    
    is_deleted = models.BooleanField(default=False, verbose_name='Eliminado', db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name='Eliminado en')
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_deleted',
        verbose_name='Eliminado por'
    )
    
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        from fixeo_project.middleware import get_current_user
        
        user = kwargs.pop('user', None)
        if not user:
            user = get_current_user()
        
        if user and user.is_authenticated:
            if not self.pk:
                self.created_by = user
            self.updated_by = user
        
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        soft = kwargs.pop('soft', True)
        
        if soft:
            self.is_deleted = True
            self.deleted_at = timezone.now()
            if user and user.is_authenticated:
                self.deleted_by = user
            self.save()
        else:
            super().delete(*args, **kwargs)

    def restore(self, user=None):
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        if user and user.is_authenticated:
            self.updated_by = user
        self.save()

    def hard_delete(self):
        super().delete()

