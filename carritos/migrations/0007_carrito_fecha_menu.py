from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('carritos', '0006_orden_comprobante_pago'),
    ]

    operations = [
        migrations.AddField(
            model_name='carrito',
            name='fecha_menu',
            field=models.DateField(
                blank=True,
                help_text='Fecha de entrega/consumo del menú diario. Un carrito = un solo día.',
                null=True,
            ),
        ),
    ]
