from django.db import migrations, models
from enums.enums import CURRENCY_CHOICES, moneda_local_desde_pais


def backfill_producto_divisa(apps, schema_editor):
    Producto = apps.get_model('empresas', 'Producto')
    for producto in Producto.objects.select_related('empresa').iterator():
        empresa = producto.empresa
        divisa = (
            getattr(empresa, 'currency', None)
            or moneda_local_desde_pais(getattr(empresa, 'pais', 'UY'))
            or 'USD'
        )
        Producto.objects.filter(pk=producto.pk).update(divisa=divisa)


class Migration(migrations.Migration):

    dependencies = [
        ('empresas', '0006_alter_empresa_currency'),
    ]

    operations = [
        migrations.AddField(
            model_name='producto',
            name='divisa',
            field=models.CharField(
                choices=CURRENCY_CHOICES,
                default='USD',
                max_length=3,
            ),
        ),
        migrations.RunPython(backfill_producto_divisa, migrations.RunPython.noop),
    ]
