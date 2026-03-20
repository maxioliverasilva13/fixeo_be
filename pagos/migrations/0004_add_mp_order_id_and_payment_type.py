from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pagos', '0003_delete_mercadopagovendedor'),
    ]

    operations = [
        migrations.AddField(
            model_name='pago',
            name='mp_order_id',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='tarjeta',
            name='payment_type',
            field=models.CharField(blank=True, default='credit_card', max_length=30),
        ),
    ]
