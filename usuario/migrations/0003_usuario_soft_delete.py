from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuario', '0002_map_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='deleted_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Eliminado en'),
        ),
        migrations.AddField(
            model_name='usuario',
            name='is_deleted',
            field=models.BooleanField(db_index=True, default=False, verbose_name='Eliminado'),
        ),
    ]
