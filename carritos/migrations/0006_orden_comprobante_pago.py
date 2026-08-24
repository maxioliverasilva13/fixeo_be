from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('carritos', '0005_menu_diario_variante'),
    ]

    operations = [
        migrations.AddField(
            model_name='orden',
            name='comprobante_pago_url',
            field=models.URLField(
                blank=True,
                default='',
                help_text='Foto/comprobante opcional al marcar el pago (transferencia/efectivo).',
                max_length=500,
            ),
        ),
        migrations.AlterField(
            model_name='orden',
            name='pago_status',
            field=models.CharField(
                blank=True,
                default='',
                help_text='MP: aprobado/liberado/… | Manual (efectivo/transferencia): pendiente/pagado/pago_en_domicilio',
                max_length=20,
            ),
        ),
    ]
