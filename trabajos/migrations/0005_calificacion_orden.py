from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('carritos', '0002_initial'),
        ('trabajos', '0004_map_efectivo_index'),
    ]

    operations = [
        migrations.AddField(
            model_name='calificacion',
            name='orden',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='calificaciones',
                to='carritos.orden',
            ),
        ),
    ]
