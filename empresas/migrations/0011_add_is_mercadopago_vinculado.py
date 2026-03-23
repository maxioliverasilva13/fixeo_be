from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('empresas', '0010_empresa_acepta_efectivo_empresa_acepta_tarjeta'),
    ]

    operations = [
        migrations.AddField(
            model_name='empresa',
            name='is_mercadopago_vinculado',
            field=models.BooleanField(default=True),
        ),
    ]
