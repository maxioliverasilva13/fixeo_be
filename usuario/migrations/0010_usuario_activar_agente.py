from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuario', '0009_email_verification_challenge'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='activar_agente',
            field=models.BooleanField(default=False, help_text='Si es True, el agente de WhatsApp responde automáticamente los mensajes entrantes de este profesional.'),
        ),
    ]
