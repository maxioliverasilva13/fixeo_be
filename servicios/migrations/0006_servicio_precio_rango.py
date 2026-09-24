from django.db import migrations, models


class Migration(migrations.Migration):
    """Precio a convenir: rango opcional por servicio (precio fijo O rango)."""

    dependencies = [
        ('servicios', '0005_backfill_servicio_imagen'),
    ]

    operations = [
        migrations.AddField(
            model_name='servicio',
            name='precio_min',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='servicio',
            name='precio_max',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
    ]
