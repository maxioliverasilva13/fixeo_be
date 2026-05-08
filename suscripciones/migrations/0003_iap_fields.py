from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('suscripciones', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='subscripcion',
            name='source',
            field=models.CharField(
                choices=[
                    ('manual', 'Manual'),
                    ('google_play', 'Google Play'),
                    ('app_store', 'App Store'),
                ],
                default='manual',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='subscripcion',
            name='status',
            field=models.CharField(
                choices=[
                    ('active', 'Active'),
                    ('trialing', 'Trialing'),
                    ('canceled', 'Canceled'),
                    ('expired', 'Expired'),
                    ('past_due', 'Past due'),
                    ('paused', 'Paused'),
                    ('refunded', 'Refunded'),
                ],
                default='active',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='subscripcion',
            name='google_play_subscription_id',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='subscripcion',
            name='google_play_purchase_token',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='subscripcion',
            name='appstore_transaction_id',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AddField(
            model_name='subscripcion',
            name='appstore_original_transaction_id',
            field=models.CharField(blank=True, db_index=True, max_length=200, null=True),
        ),
    ]
