from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuario_localizacion', '0001_initial'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='usuariolocalizacion',
            index=models.Index(
                fields=['es_principal', 'usuario'],
                name='idx_ul_principal_usuario',
            ),
        ),
        migrations.AddIndex(
            model_name='usuariolocalizacion',
            index=models.Index(
                fields=['localizacion'],
                name='idx_ul_localizacion',
            ),
        ),
    ]
