from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('empresas', '0013_menu_diario'),
    ]

    operations = [
        migrations.AddField(
            model_name='productodia',
            name='activo',
            field=models.BooleanField(
                default=True,
                help_text='Si es False, el plato sigue vinculado al día pero no se ofrece al cliente.',
            ),
        ),
    ]
