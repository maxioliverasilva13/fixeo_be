from django.contrib.auth.hashers import make_password
from django.db import migrations, models


ADD_COLUMN_SQL = """
ALTER TABLE empresa
    ADD COLUMN IF NOT EXISTS tiene_landing_page boolean NOT NULL DEFAULT false;
"""


def create_admin_user(apps, schema_editor):
    """Best-effort: no debe tumbar la migración si el user ya existe o falla el seed."""
    try:
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
    except Exception:
        # La columna ya se agregó; el admin se puede crear con seed_admin.
        pass


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('empresas', '0011_empresa_landing_fields'),
        ('usuario', '0009_email_verification_challenge'),
        ('rol', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='empresa',
                    name='tiene_landing_page',
                    field=models.BooleanField(
                        default=False,
                        help_text='Si es True, la empresa tiene landing page aunque su plan no la incluya.',
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(ADD_COLUMN_SQL, migrations.RunSQL.noop),
            ],
        ),
        migrations.RunPython(create_admin_user, noop_reverse),
    ]
