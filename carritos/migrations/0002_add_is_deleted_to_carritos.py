# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('carritos', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='carrito',
            name='is_deleted',
            field=models.BooleanField(db_index=True, default=False, verbose_name='Eliminado'),
        ),
        migrations.AddField(
            model_name='carritoitem',
            name='is_deleted',
            field=models.BooleanField(db_index=True, default=False, verbose_name='Eliminado'),
        ),
        migrations.AddField(
            model_name='orden',
            name='is_deleted',
            field=models.BooleanField(db_index=True, default=False, verbose_name='Eliminado'),
        ),
        migrations.AddField(
            model_name='ordenitem',
            name='is_deleted',
            field=models.BooleanField(db_index=True, default=False, verbose_name='Eliminado'),
        ),
    ]
