from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('empresas', '0010_empresa_mapa_subdomain'),
    ]

    operations = [
        migrations.AddField(
            model_name='empresa',
            name='landing_titulo',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Título principal de la landing (opcional, usa nombre si está vacío).',
                max_length=200,
            ),
        ),
        migrations.AddField(
            model_name='empresa',
            name='landing_slogan',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Slogan o frase corta para la landing.',
                max_length=300,
            ),
        ),
        migrations.AddField(
            model_name='empresa',
            name='landing_descripcion',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Descripción extendida para la landing (opcional, usa descripcion si está vacía).',
            ),
        ),
        migrations.AddField(
            model_name='empresa',
            name='landing_foto_url',
            field=models.URLField(
                blank=True,
                default='',
                help_text='Imagen de portada o logo para la landing.',
                max_length=500,
            ),
        ),
    ]
