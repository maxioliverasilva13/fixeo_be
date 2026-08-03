import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UsuarioBlock',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Creado en')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Actualizado en')),
                ('is_deleted', models.BooleanField(db_index=True, default=False, verbose_name='Eliminado')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='Eliminado en')),
                ('reason', models.CharField(blank=True, default='', max_length=255)),
                ('blocked', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='blocks_received', to=settings.AUTH_USER_MODEL)),
                ('blocker', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='blocks_made', to=settings.AUTH_USER_MODEL)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL, verbose_name='Creado por')),
                ('deleted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_deleted', to=settings.AUTH_USER_MODEL, verbose_name='Eliminado por')),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated', to=settings.AUTH_USER_MODEL, verbose_name='Actualizado por')),
            ],
            options={
                'verbose_name': 'Bloqueo de usuario',
                'verbose_name_plural': 'Bloqueos de usuario',
                'db_table': 'moderacion_usuario_block',
            },
        ),
        migrations.CreateModel(
            name='ContentReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Creado en')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Actualizado en')),
                ('is_deleted', models.BooleanField(db_index=True, default=False, verbose_name='Eliminado')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='Eliminado en')),
                ('content_type', models.CharField(choices=[('message', 'Mensaje'), ('chat', 'Chat'), ('profile', 'Perfil'), ('rating', 'Calificación'), ('other', 'Otro')], max_length=20)),
                ('content_id', models.PositiveIntegerField(blank=True, null=True)),
                ('reason', models.CharField(choices=[('spam', 'Spam'), ('harassment', 'Acoso o abuso'), ('hate', 'Discurso de odio'), ('sexual', 'Contenido sexual'), ('scam', 'Estafa o fraude'), ('other', 'Otro')], default='other', max_length=30)),
                ('details', models.TextField(blank=True, default='')),
                ('status', models.CharField(choices=[('pending', 'Pendiente'), ('reviewed', 'En revisión'), ('actioned', 'Acción tomada'), ('dismissed', 'Descartado')], default='pending', max_length=20)),
                ('admin_notes', models.TextField(blank=True, default='')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_created', to=settings.AUTH_USER_MODEL, verbose_name='Creado por')),
                ('deleted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_deleted', to=settings.AUTH_USER_MODEL, verbose_name='Eliminado por')),
                ('reported_user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='reports_received', to=settings.AUTH_USER_MODEL)),
                ('reporter', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reports_made', to=settings.AUTH_USER_MODEL)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_updated', to=settings.AUTH_USER_MODEL, verbose_name='Actualizado por')),
            ],
            options={
                'verbose_name': 'Reporte de contenido',
                'verbose_name_plural': 'Reportes de contenido',
                'db_table': 'moderacion_content_report',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='usuarioblock',
            constraint=models.UniqueConstraint(fields=('blocker', 'blocked'), name='uniq_usuario_block_pair'),
        ),
        migrations.AddIndex(
            model_name='contentreport',
            index=models.Index(fields=['status', '-created_at'], name='moderacion__status_7a0c1a_idx'),
        ),
        migrations.AddIndex(
            model_name='contentreport',
            index=models.Index(fields=['reported_user', '-created_at'], name='moderacion__reporte_4d2b9e_idx'),
        ),
    ]
