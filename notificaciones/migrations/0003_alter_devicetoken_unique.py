# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notificaciones', '0002_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='devicetoken',
            name='device_token',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterUniqueTogether(
            name='devicetoken',
            unique_together={('device_token', 'usuario')},
        ),
    ]
