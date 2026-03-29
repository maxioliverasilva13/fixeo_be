from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('empresas', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='empresa',
            name='mp_access_token',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='empresa',
            name='mp_refresh_token',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='empresa',
            name='mp_user_id',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AddField(
            model_name='empresa',
            name='mp_email',
            field=models.EmailField(blank=True, default='', max_length=254),
        ),
        migrations.AlterField(
            model_name='empresa',
            name='is_mercadopago_vinculado',
            field=models.BooleanField(default=False),
        ),
    ]
