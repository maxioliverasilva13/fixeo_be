from django.db import migrations, models


class Migration(migrations.Migration):
    """Precio personalizado en trabajos: rango congelado + precio estimado."""

    dependencies = [
        ('trabajos', '0012_trabajo_recordatorios_ensure'),
    ]

    operations = [
        migrations.AddField(
            model_name='trabajo',
            name='precio_min',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='trabajo',
            name='precio_max',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='trabajo',
            name='precio_estimado',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='trabajo',
            name='requiere_estimacion_precio',
            field=models.BooleanField(
                default=False,
                help_text='Si es True, el profesional debe estimar el precio dentro del rango al aceptar.',
            ),
        ),
    ]
