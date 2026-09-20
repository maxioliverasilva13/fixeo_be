import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('empresas', '0014_productodia_activo'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductoImagen',
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
                ('producto', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='imagenes', to='empresas.producto')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated', to=settings.AUTH_USER_MODEL, verbose_name='Actualizado por')),
            ],
            options={
                'verbose_name': 'Imagen de producto',
                'verbose_name_plural': 'Imágenes de producto',
                'db_table': 'producto_imagen',
                'ordering': ['orden', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='productoimagen',
            index=models.Index(fields=['producto', 'orden'], name='idx_producto_imagen_orden'),
        ),
    ]
