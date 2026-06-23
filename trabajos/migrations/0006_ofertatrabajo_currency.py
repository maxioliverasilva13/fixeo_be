from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trabajos', '0005_calificacion_orden'),
    ]

    operations = [
        migrations.AddField(
            model_name='ofertatrabajo',
            name='currency',
            field=models.CharField(blank=True, max_length=3, null=True),
        ),
    ]
