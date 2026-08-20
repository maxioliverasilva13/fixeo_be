from django.db import migrations


VENDEDOR_NOMBRE = 'Vendedor@'
VENDEDOR_DESCRIPCION = 'Venta de productos físicos y catálogo online'


def seed_vendedor(apps, schema_editor):
    Profesion = apps.get_model('profesion', 'Profesion')
    Profesion.objects.get_or_create(
        nombre=VENDEDOR_NOMBRE,
        defaults={
            'descripcion': VENDEDOR_DESCRIPCION,
            'logo_svg_url': '',
            'is_deleted': False,
        },
    )


def unseed_vendedor(apps, schema_editor):
    Profesion = apps.get_model('profesion', 'Profesion')
    Profesion.objects.filter(nombre=VENDEDOR_NOMBRE).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('profesion', '0002_initial'),
    ]

    operations = [
        migrations.RunPython(seed_vendedor, unseed_vendedor),
    ]
