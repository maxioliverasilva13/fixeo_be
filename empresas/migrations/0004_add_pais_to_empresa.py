from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('empresas', '0003_add_mp_oauth_fields_to_empresa'),
    ]

    operations = [
        migrations.AddField(
            model_name='empresa',
            name='pais',
            field=models.CharField(
                choices=[
                    ('AR', 'Argentina'), ('BO', 'Bolivia'), ('BR', 'Brasil'),
                    ('CL', 'Chile'), ('CO', 'Colombia'), ('CR', 'Costa Rica'),
                    ('CU', 'Cuba'), ('DO', 'República Dominicana'), ('EC', 'Ecuador'),
                    ('GT', 'Guatemala'), ('HN', 'Honduras'), ('MX', 'México'),
                    ('NI', 'Nicaragua'), ('PA', 'Panamá'), ('PE', 'Perú'),
                    ('PR', 'Puerto Rico'), ('PY', 'Paraguay'), ('SV', 'El Salvador'),
                    ('UY', 'Uruguay'), ('VE', 'Venezuela'),
                ],
                default='UY',
                max_length=5,
            ),
        ),
    ]
