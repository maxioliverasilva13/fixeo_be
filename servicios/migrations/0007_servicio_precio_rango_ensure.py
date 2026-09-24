from django.db import migrations


# Ver nota en trabajos/0011: reparación idempotente del esquema.
ADD_COLUMNS_SQL = """
ALTER TABLE usuario_servicios
    ADD COLUMN IF NOT EXISTS precio_min numeric(10, 2) NULL,
    ADD COLUMN IF NOT EXISTS precio_max numeric(10, 2) NULL;
"""


class Migration(migrations.Migration):
    """Garantiza usuario_servicios.precio_min/precio_max incluso si servicios.0006 quedó faked."""

    dependencies = [
        ('servicios', '0006_servicio_precio_rango'),
    ]

    operations = [
        migrations.RunSQL(ADD_COLUMNS_SQL, migrations.RunSQL.noop),
    ]
