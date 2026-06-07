from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuario', '0001_initial'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='usuario',
            index=models.Index(
                fields=['is_owner_empresa', 'is_active'],
                name='idx_usuario_mapa_empresa',
            ),
        ),
    ]
