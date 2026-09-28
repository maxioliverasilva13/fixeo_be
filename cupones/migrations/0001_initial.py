import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('empresas', '0016_backfill_producto_imagen'),
        ('carritos', '0009_orden_phonenumberinviteduser_ensure'),
        ('trabajos', '0012_trabajo_recordatorios_ensure'),
    ]

    operations = [
        migrations.CreateModel(
            name='Cupon',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Creado en')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Actualizado en')),
                ('is_deleted', models.BooleanField(db_index=True, default=False, verbose_name='Eliminado')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='Eliminado en')),
                ('codigo', models.CharField(editable=False, max_length=20, unique=True)),
                ('tipo_descuento', models.CharField(choices=[('porcentaje', 'Porcentaje'), ('monto_fijo', 'Monto fijo')], max_length=20)),
                ('valor', models.DecimalField(decimal_places=2, max_digits=10)),
                ('fecha_expiracion', models.DateTimeField(blank=True, null=True)),
                ('fecha_uso', models.DateTimeField(blank=True, null=True)),
                ('cliente', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cupones_recibidos', to=settings.AUTH_USER_MODEL)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL, verbose_name='Creado por')),
                ('deleted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_deleted', to=settings.AUTH_USER_MODEL, verbose_name='Eliminado por')),
                ('empresa', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cupones', to='empresas.empresa')),
                ('orden', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cupones_usados', to='carritos.orden')),
                ('trabajo', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cupones_usados', to='trabajos.trabajo')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated', to=settings.AUTH_USER_MODEL, verbose_name='Actualizado por')),
            ],
            options={
                'verbose_name': 'Cupón',
                'verbose_name_plural': 'Cupones',
                'db_table': 'cupon',
            },
        ),
        migrations.AddIndex(
            model_name='cupon',
            index=models.Index(fields=['codigo'], name='cupon_codigo_idx'),
        ),
        migrations.AddIndex(
            model_name='cupon',
            index=models.Index(fields=['empresa', 'cliente'], name='cupon_empresa_cliente_idx'),
        ),
    ]
