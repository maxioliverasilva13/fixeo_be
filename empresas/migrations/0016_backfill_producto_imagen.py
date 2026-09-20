from django.db import migrations


def backfill_producto_imagen(apps, schema_editor):
    Producto = apps.get_model('empresas', 'Producto')
    ProductoImagen = apps.get_model('empresas', 'ProductoImagen')

    productos = Producto.objects.filter(is_deleted=False).exclude(foto='').exclude(foto__isnull=True)
    for producto in productos.iterator():
        if not ProductoImagen.objects.filter(producto_id=producto.id, is_deleted=False).exists():
            ProductoImagen.objects.create(producto_id=producto.id, url=producto.foto, orden=0)


def reverse_backfill(apps, schema_editor):
    ProductoImagen = apps.get_model('empresas', 'ProductoImagen')
    ProductoImagen.objects.filter(orden=0).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('empresas', '0015_producto_imagen'),
    ]

    operations = [
        migrations.RunPython(backfill_producto_imagen, reverse_backfill),
    ]
