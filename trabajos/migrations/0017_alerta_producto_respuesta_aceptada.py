from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('trabajos', '0016_alerta_producto_urgente'),
    ]

    operations = [
        migrations.AddField(
            model_name='alertaproductourgente',
            name='respuesta_aceptada',
            field=models.ForeignKey(
                blank=True,
                help_text='Propuesta con la que el usuario resolvió la alerta.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+',
                to='trabajos.respuestaalertaproducto',
            ),
        ),
    ]
