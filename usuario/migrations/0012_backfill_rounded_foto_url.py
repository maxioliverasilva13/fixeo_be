from django.db import migrations, models


def backfill_rounded_foto_url(apps, schema_editor):
    Usuario = apps.get_model('usuario', 'Usuario')
    Usuario.objects.filter(foto_url__isnull=False).exclude(foto_url='').filter(
        models.Q(rounded_foto_url__isnull=True) | models.Q(rounded_foto_url='')
    ).update(rounded_foto_url=models.F('foto_url'))


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('usuario', '0011_usuario_activar_agente_ensure'),
    ]

    operations = [
        migrations.RunPython(backfill_rounded_foto_url, noop),
    ]
