from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trabajos', '0006_ofertatrabajo_currency'),
    ]

    operations = [
        migrations.AddField(
            model_name='calificacion',
            name='direccion',
            field=models.CharField(
                choices=[
                    ('cliente_a_profesional', 'Cliente a profesional'),
                    ('profesional_a_cliente', 'Profesional a cliente'),
                ],
                default='cliente_a_profesional',
                max_length=32,
            ),
        ),
    ]
