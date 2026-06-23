from django.db import migrations, models


def backfill_producto_modalidad(apps, schema_editor):
    Producto = apps.get_model('empresas', 'Producto')
    for producto in Producto.objects.select_related('empresa__admin_id').all():
        admin = producto.empresa.admin_id
        producto.acepta_domicilio = bool(getattr(admin, 'trabajo_domicilio', True))
        producto.acepta_retiro = bool(getattr(admin, 'trabajo_local', True))
        if not producto.acepta_domicilio and not producto.acepta_retiro:
            producto.acepta_domicilio = True
        producto.save(update_fields=['acepta_domicilio', 'acepta_retiro'])


class Migration(migrations.Migration):

    dependencies = [
        ('empresas', '0008_sync_empresa_currency_from_pais'),
    ]

    operations = [
        migrations.AddField(
            model_name='producto',
            name='acepta_domicilio',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='producto',
            name='acepta_retiro',
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(backfill_producto_modalidad, migrations.RunPython.noop),
    ]
