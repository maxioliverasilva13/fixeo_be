from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuario', '0007_usuario_token_ultima_actividad'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='recibir_correos',
            field=models.BooleanField(
                default=True,
                help_text='Si es True, el usuario recibe emails de notificación.',
            ),
        ),
        migrations.AddField(
            model_name='usuario',
            name='recibir_notificaciones',
            field=models.BooleanField(
                default=True,
                help_text='Si es True, el usuario recibe push notifications.',
            ),
        ),
    ]
