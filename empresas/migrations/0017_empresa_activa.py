from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('empresas', '0016_backfill_producto_imagen'),
    ]

    operations = [
        migrations.AddField(
            model_name='empresa',
            name='activa',
            field=models.BooleanField(
                default=True,
                help_text=(
                    'Si es False, la empresa queda desactivada por admin: no aparece en búsquedas, '
                    'mapa ni endpoints de zona. No se borra físicamente.'
                ),
            ),
        ),
    ]
