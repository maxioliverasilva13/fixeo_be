# Generated manually for trabajos urgentes

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('trabajos', '0005_trabajo_es_domicilio_profesional_and_more'),
        ('profesion', '0002_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='trabajo',
            name='precio_final',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AlterField(
            model_name='trabajo',
            name='status',
            field=models.CharField(
                choices=[
                    ('pendiente', 'Pendiente'), 
                    ('pendiente_urgente', 'Pendiente Urgente'), 
                    ('aceptado', 'Aceptado'), 
                    ('finalizado', 'Finalizado'), 
                    ('cancelado', 'Cancelado')
                ], 
                default='pendiente', 
                max_length=20
            ),
        ),
        migrations.AddField(
            model_name='trabajo',
            name='profesion_urgente',
            field=models.ForeignKey(
                blank=True, 
                null=True, 
                on_delete=django.db.models.deletion.SET_NULL, 
                related_name='trabajos_urgentes', 
                to='profesion.profesion'
            ),
        ),
        migrations.AddField(
            model_name='trabajo',
            name='radio_busqueda_km',
            field=models.DecimalField(
                blank=True, 
                decimal_places=2, 
                help_text='Radio de búsqueda para trabajos urgentes', 
                max_digits=5, 
                null=True
            ),
        ),
        migrations.CreateModel(
            name='OfertaTrabajo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Creado en')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Actualizado en')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='Eliminado en')),
                ('is_deleted', models.BooleanField(db_index=True, default=False, verbose_name='Eliminado')),
                ('precio_ofertado', models.DecimalField(decimal_places=2, max_digits=10)),
                ('tiempo_estimado', models.IntegerField(help_text='Tiempo estimado en minutos')),
                ('mensaje', models.TextField(blank=True, null=True)),
                ('status', models.CharField(choices=[('pendiente', 'Pendiente'), ('aceptada', 'Aceptada'), ('rechazada', 'Rechazada')], default='pendiente', max_length=20)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL, verbose_name='Creado por')),
                ('deleted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_deleted', to=settings.AUTH_USER_MODEL, verbose_name='Eliminado por')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated', to=settings.AUTH_USER_MODEL, verbose_name='Actualizado por')),
                ('profesional', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ofertas_realizadas', to=settings.AUTH_USER_MODEL)),
                ('trabajo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ofertas', to='trabajos.trabajo')),
            ],
            options={
                'verbose_name': 'Oferta de Trabajo',
                'verbose_name_plural': 'Ofertas de Trabajo',
                'db_table': 'oferta_trabajo',
                'ordering': ['-created_at'],
                'unique_together': {('trabajo', 'profesional')},
            },
        ),
    ]
