from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuario_profesion', '0001_initial'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='usuarioprofesion',
            index=models.Index(
                fields=['profesion', 'usuario'],
                name='idx_up_profesion_usuario',
            ),
        ),
    ]
