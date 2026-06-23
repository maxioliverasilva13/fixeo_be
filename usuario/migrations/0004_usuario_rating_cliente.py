from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuario', '0003_usuario_soft_delete'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='cant_calif_cliente',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='usuario',
            name='rating_cliente',
            field=models.FloatField(default=0),
        ),
    ]
