from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trabajos', '0007_calificacion_direccion'),
    ]

    operations = [
        migrations.AddField(
            model_name='ofertatrabajo',
            name='motivo_rechazo',
            field=models.TextField(blank=True, null=True),
        ),
    ]
