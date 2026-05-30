from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('suscripciones', '0003_iap_fields'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='subscripcion',
            index=models.Index(
                fields=['user_id', 'cancelada', 'expiracion'],
                name='idx_sub_user_active',
            ),
        ),
        migrations.AddIndex(
            model_name='plan',
            index=models.Index(
                fields=['precio', 'cantidad_jobs'],
                name='idx_plan_rank',
            ),
        ),
    ]
