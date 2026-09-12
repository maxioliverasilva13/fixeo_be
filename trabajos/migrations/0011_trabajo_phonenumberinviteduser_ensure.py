from django.db import migrations


# Ver nota en usuario/0011: reparación idempotente del esquema.
ADD_COLUMN_SQL = """
ALTER TABLE trabajo
    ADD COLUMN IF NOT EXISTS "phoneNumberInvitedUser" varchar(32) NOT NULL DEFAULT '';
"""


class Migration(migrations.Migration):
    """Garantiza trabajo.phoneNumberInvitedUser incluso si trabajos.0009 quedó faked."""

    dependencies = [
        ('trabajos', '0010_trabajo_recordatorio_12h_enviado_at_and_more'),
    ]

    operations = [
        migrations.RunSQL(ADD_COLUMN_SQL, migrations.RunSQL.noop),
    ]
