from django.db import migrations


# Ver nota en trabajos/0011: reparación idempotente del esquema.
ADD_COLUMNS_SQL = """
ALTER TABLE trabajo
    ADD COLUMN IF NOT EXISTS precio_min numeric(10, 2) NULL,
    ADD COLUMN IF NOT EXISTS precio_max numeric(10, 2) NULL,
    ADD COLUMN IF NOT EXISTS precio_estimado numeric(10, 2) NULL,
    ADD COLUMN IF NOT EXISTS requiere_estimacion_precio boolean NOT NULL DEFAULT false;
"""


class Migration(migrations.Migration):
    """Garantiza trabajo.precio_min/precio_max/precio_estimado/requiere_estimacion_precio
    incluso si trabajos.0013 quedó faked."""

    dependencies = [
        ('trabajos', '0013_trabajo_precio_rango'),
    ]

    operations = [
        migrations.RunSQL(ADD_COLUMNS_SQL, migrations.RunSQL.noop),
    ]
