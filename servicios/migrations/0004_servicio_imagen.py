import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('servicios', '0003_servicio_modalidad_entrega'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ServicioImagen',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Creado en')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Actualizado en')),
                ('is_deleted', models.BooleanField(db_index=True, default=False, verbose_name='Eliminado')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='Eliminado en')),
                ('url', models.URLField(max_length=500)),
                ('orden', models.PositiveSmallIntegerField(default=0)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL, verbose_name='Creado por')),
                ('deleted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_deleted', to=settings.AUTH_USER_MODEL, verbose_name='Eliminado por')),
                ('servicio', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='imagenes', to='servicios.servicio')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated', to=settings.AUTH_USER_MODEL, verbose_name='Actualizado por')),
            ],
            options={
                'verbose_name': 'Imagen de servicio',
                'verbose_name_plural': 'Imágenes de servicio',
                'db_table': 'servicio_imagen',
                'ordering': ['orden', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='servicioimagen',
            index=models.Index(fields=['servicio', 'orden'], name='idx_servicio_imagen_orden'),
        ),
    ]
