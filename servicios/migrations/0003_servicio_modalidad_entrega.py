from django.db import migrations, models


def backfill_servicio_modalidad(apps, schema_editor):
    Servicio = apps.get_model('servicios', 'Servicio')
    for servicio in Servicio.objects.select_related('usuario').all():
        usuario = servicio.usuario
        servicio.acepta_domicilio = bool(getattr(usuario, 'trabajo_domicilio', True))
        servicio.acepta_retiro = bool(getattr(usuario, 'trabajo_local', True))
        if not servicio.acepta_domicilio and not servicio.acepta_retiro:
            servicio.acepta_domicilio = True
        servicio.save(update_fields=['acepta_domicilio', 'acepta_retiro'])


class Migration(migrations.Migration):

    dependencies = [
        ('servicios', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='servicio',
            name='acepta_domicilio',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='servicio',
            name='acepta_retiro',
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(backfill_servicio_modalidad, migrations.RunPython.noop),
    ]
