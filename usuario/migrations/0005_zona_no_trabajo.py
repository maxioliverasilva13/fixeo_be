from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('usuario', '0004_usuario_rating_cliente'),
    ]

    operations = [
        migrations.CreateModel(
            name='ZonaNoTrabajo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Creado en')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Actualizado en')),
                ('is_deleted', models.BooleanField(db_index=True, default=False, verbose_name='Eliminado')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='Eliminado en')),
                ('nombre', models.CharField(blank=True, default='', max_length=100)),
                ('latitud', models.DecimalField(decimal_places=7, max_digits=10)),
                ('longitud', models.DecimalField(decimal_places=7, max_digits=10)),
                ('radio_km', models.DecimalField(decimal_places=2, max_digits=5)),
                ('activa', models.BooleanField(default=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to='usuario.usuario', verbose_name='Creado por')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated', to='usuario.usuario', verbose_name='Actualizado por')),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='zonas_no_trabajo', to='usuario.usuario')),
            ],
            options={
                'verbose_name': 'Zona de no trabajo',
                'verbose_name_plural': 'Zonas de no trabajo',
                'db_table': 'zona_no_trabajo',
                'indexes': [models.Index(fields=['usuario', 'activa'], name='idx_zona_no_trabajo_user')],
            },
        ),
    ]
