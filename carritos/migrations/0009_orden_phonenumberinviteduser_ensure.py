from django.db import migrations


# Ver nota en usuario/0011: reparación idempotente del esquema.
ADD_COLUMN_SQL = """
ALTER TABLE orden
    ADD COLUMN IF NOT EXISTS "phoneNumberInvitedUser" varchar(32) NOT NULL DEFAULT '';
"""


class Migration(migrations.Migration):
    """Garantiza orden.phoneNumberInvitedUser incluso si carritos.0008 quedó faked."""

    dependencies = [
        ('carritos', '0008_orden_phonenumberinviteduser'),
    ]

    operations = [
        migrations.RunSQL(ADD_COLUMN_SQL, migrations.RunSQL.noop),
    ]
