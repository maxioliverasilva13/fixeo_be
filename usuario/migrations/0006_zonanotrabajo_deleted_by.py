from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('usuario', '0005_zona_no_trabajo'),
    ]

    operations = [
        migrations.AddField(
            model_name='zonanotrabajo',
            name='deleted_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='%(class)s_deleted',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Eliminado por',
            ),
        ),
    ]
