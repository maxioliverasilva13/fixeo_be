from django.db import migrations
from enums.enums import moneda_local_desde_pais


def sync_empresa_currency_from_pais(apps, schema_editor):
    Empresa = apps.get_model('empresas', 'Empresa')
    for empresa in Empresa.objects.all().iterator():
        local = moneda_local_desde_pais(empresa.pais)
        if empresa.currency != local:
            Empresa.objects.filter(pk=empresa.pk).update(currency=local)


class Migration(migrations.Migration):

    dependencies = [
        ('empresas', '0007_producto_divisa'),
    ]

    operations = [
        migrations.RunPython(sync_empresa_currency_from_pais, migrations.RunPython.noop),
    ]
