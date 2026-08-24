import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('empresas', '0012_empresa_tiene_landing_page'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='empresa',
            name='vende_menu_diario',
            field=models.BooleanField(
                default=False,
                help_text='Si es True, la empresa ofrece menú diario (carta por día de la semana).',
            ),
        ),
        migrations.AddField(
            model_name='producto',
            name='es_menu_diario',
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text='Si es True, el producto es un plato de menú diario (no catálogo retail).',
            ),
        ),
        migrations.AddIndex(
            model_name='producto',
            index=models.Index(fields=['empresa', 'es_menu_diario'], name='idx_producto_empresa_menu'),
        ),
        migrations.CreateModel(
            name='ProductoDia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Creado en')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Actualizado en')),
                ('is_deleted', models.BooleanField(db_index=True, default=False, verbose_name='Eliminado')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='Eliminado en')),
                ('dia_semana', models.PositiveSmallIntegerField(help_text='1=Lunes … 7=Domingo (mismo convenio que horarios).')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL, verbose_name='Creado por')),
                ('deleted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_deleted', to=settings.AUTH_USER_MODEL, verbose_name='Eliminado por')),
                ('producto', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='dias_menu', to='empresas.producto')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated', to=settings.AUTH_USER_MODEL, verbose_name='Actualizado por')),
            ],
            options={
                'verbose_name': 'Día de menú',
                'verbose_name_plural': 'Días de menú',
                'db_table': 'producto_dia',
                'unique_together': {('producto', 'dia_semana')},
            },
        ),
        migrations.CreateModel(
            name='ProductoVariante',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Creado en')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Actualizado en')),
                ('is_deleted', models.BooleanField(db_index=True, default=False, verbose_name='Eliminado')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='Eliminado en')),
                ('nombre', models.CharField(max_length=200)),
                ('precio_extra', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('activo', models.BooleanField(default=True)),
                ('orden', models.PositiveSmallIntegerField(default=0)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL, verbose_name='Creado por')),
                ('deleted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_deleted', to=settings.AUTH_USER_MODEL, verbose_name='Eliminado por')),
                ('producto', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='variantes', to='empresas.producto')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated', to=settings.AUTH_USER_MODEL, verbose_name='Actualizado por')),
            ],
            options={
                'verbose_name': 'Variante de producto',
                'verbose_name_plural': 'Variantes de producto',
                'db_table': 'producto_variante',
                'ordering': ['orden', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='productodia',
            index=models.Index(fields=['dia_semana'], name='idx_producto_dia_semana'),
        ),
    ]
