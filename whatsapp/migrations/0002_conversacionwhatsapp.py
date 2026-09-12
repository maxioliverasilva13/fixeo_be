import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('whatsapp', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConversacionWhatsApp',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('wa_id', models.CharField(db_index=True, max_length=32, unique=True)),
                ('flujo', models.CharField(choices=[('cliente', 'Cliente'), ('onboarding_profesional', 'Onboarding profesional')], default='cliente', max_length=32)),
                ('estado', models.CharField(choices=[('idle', 'Inactivo'), ('esperando_ubicacion', 'Esperando ubicación'), ('recolectando_datos_prof', 'Recolectando datos profesional'), ('confirmando_reserva', 'Confirmando reserva'), ('armando_pedido', 'Armando pedido'), ('confirmando_pedido', 'Confirmando pedido')], default='idle', max_length=32)),
                ('ubicacion_lat', models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ('ubicacion_lon', models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True)),
                ('ciudad', models.CharField(blank=True, default='', max_length=120)),
                ('pais', models.CharField(blank=True, default='', max_length=80)),
                ('slots', models.JSONField(blank=True, default=dict)),
                ('historial', models.JSONField(blank=True, default=list)),
                ('ultima_actividad', models.DateTimeField(auto_now=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('usuario', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='conversaciones_whatsapp', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Conversación de WhatsApp',
                'verbose_name_plural': 'Conversaciones de WhatsApp',
                'ordering': ['-ultima_actividad'],
            },
        ),
    ]
