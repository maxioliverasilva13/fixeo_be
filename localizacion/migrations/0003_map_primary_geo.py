from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('localizacion', '0002_initial'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='localizacion',
            index=models.Index(
                fields=['isPrimary', 'latitud', 'longitud'],
                name='idx_loc_primary_geo',
            ),
        ),
    ]
