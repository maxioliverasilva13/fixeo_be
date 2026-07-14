from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuario', '0008_usuario_preferencias_notificacion'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailVerificationChallenge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(db_index=True, max_length=254)),
                ('code', models.CharField(max_length=6)),
                ('verification_token', models.UUIDField(blank=True, db_index=True, null=True, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('verified_at', models.DateTimeField(blank=True, null=True)),
                ('used_at', models.DateTimeField(blank=True, null=True)),
                ('attempts', models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                'db_table': 'email_verification_challenge',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='emailverificationchallenge',
            index=models.Index(fields=['email', 'created_at'], name='idx_email_verif_email_created'),
        ),
    ]
