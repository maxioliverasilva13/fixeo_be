from django.db import migrations


# Igual que empresas/0012: ALTER idempotente para reparar bases donde la
# migración quedó registrada en django_migrations pero la columna nunca se creó
# (el start de Railway "fakes" migraciones cuando `migrate` falla).
ADD_COLUMN_SQL = """
ALTER TABLE usuario
    ADD COLUMN IF NOT EXISTS activar_agente boolean NOT NULL DEFAULT false;
"""


class Migration(migrations.Migration):
    """Garantiza usuario.activar_agente incluso si usuario.0010 quedó faked.

    No toca el estado de Django (la columna ya está declarada en 0010), sólo
    asegura el esquema físico.
    """

    dependencies = [
        ('usuario', '0010_usuario_activar_agente'),
    ]

    operations = [
        migrations.RunSQL(ADD_COLUMN_SQL, migrations.RunSQL.noop),
    ]
