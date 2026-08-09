from django.contrib.auth.hashers import make_password
from django.db import migrations, models


def create_admin_user(apps, schema_editor):
    Usuario = apps.get_model('usuario', 'Usuario')
    Rol = apps.get_model('rol', 'Rol')

    rol_admin, _ = Rol.objects.get_or_create(nombre='admin')

    if Usuario.objects.filter(correo='admin@gmail.com').exists():
        return

    Usuario.objects.create(
        correo='admin@gmail.com',
        password=make_password('admin1234'),
        nombre='Admin',
        apellido='Sistema',
        telefono='',
        is_staff=True,
        is_superuser=True,
        is_active=True,
        is_owner_empresa=False,
        rol=rol_admin,
    )


def remove_admin_user(apps, schema_editor):
    Usuario = apps.get_model('usuario', 'Usuario')
    Usuario.objects.filter(correo='admin@gmail.com').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('empresas', '0011_empresa_landing_fields'),
        ('usuario', '0009_email_verification_challenge'),
        ('rol', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='empresa',
            name='tiene_landing_page',
            field=models.BooleanField(
                default=False,
                help_text='Si es True, la empresa tiene landing page aunque su plan no la incluya.',
            ),
        ),
        migrations.RunPython(create_admin_user, remove_admin_user),
    ]
