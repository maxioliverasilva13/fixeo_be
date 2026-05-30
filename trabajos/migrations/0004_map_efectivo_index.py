from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trabajos', '0003_trabajo_currency'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='trabajo',
            index=models.Index(
                fields=['profesional', 'metodo_pago', 'created_at'],
                name='idx_trabajo_prof_efectivo',
            ),
        ),
    ]
