from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuario', '0006_zonanotrabajo_deleted_by'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='token_ultima_actividad',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
