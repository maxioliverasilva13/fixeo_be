from django.db import migrations


def backfill_servicio_imagen(apps, schema_editor):
    Servicio = apps.get_model('servicios', 'Servicio')
    ServicioImagen = apps.get_model('servicios', 'ServicioImagen')

    servicios = Servicio.objects.filter(is_deleted=False).exclude(foto='').exclude(foto__isnull=True)
    for servicio in servicios.iterator():
        if not ServicioImagen.objects.filter(servicio_id=servicio.id, is_deleted=False).exists():
            ServicioImagen.objects.create(servicio_id=servicio.id, url=servicio.foto, orden=0)


def reverse_backfill(apps, schema_editor):
    ServicioImagen = apps.get_model('servicios', 'ServicioImagen')
    ServicioImagen.objects.filter(orden=0).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('servicios', '0004_servicio_imagen'),
    ]

    operations = [
        migrations.RunPython(backfill_servicio_imagen, reverse_backfill),
    ]
