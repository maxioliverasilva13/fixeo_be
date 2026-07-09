from django.db import migrations, models


def set_pro_landing(apps, schema_editor):
    Plan = apps.get_model('suscripciones', 'Plan')
    Plan.objects.filter(nombre='Pro').update(tiene_landing_page=True)


class Migration(migrations.Migration):

    dependencies = [
        ('suscripciones', '0004_map_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='plan',
            name='tiene_landing_page',
            field=models.BooleanField(
                default=False,
                help_text='Si es True, las empresas con este plan pueden tener landing page pública.',
            ),
        ),
        migrations.RunPython(set_pro_landing, migrations.RunPython.noop),
    ]
