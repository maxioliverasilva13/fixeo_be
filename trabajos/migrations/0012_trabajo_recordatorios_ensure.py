import uuid

from django.db import migrations

UNIQUE_INDEX_NAME = "trabajo_token_confirmacion_uniq"


def _columnas(connection, table):
    with connection.cursor() as cursor:
        return {
            column.name
            for column in connection.introspection.get_table_description(cursor, table)
        }


def _token_es_unico(connection, table):
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, table)
    return any(
        constraint.get("unique")
        and list(constraint.get("columns") or []) == ["token_confirmacion"]
        for constraint in constraints.values()
    )


def ensure_trabajo_recordatorios(apps, schema_editor):
    """Repara las columnas de trabajos.0010 si quedó registrada sin ejecutar su DDL.

    Réplica idempotente de 0010: agrega los dos datetime y token_confirmacion
    (sin unique), regenera un uuid por fila y recién ahí crea el índice único.
    """
    Trabajo = apps.get_model("trabajos", "Trabajo")
    table = Trabajo._meta.db_table
    connection = schema_editor.connection

    columnas = _columnas(connection, table)

    for nombre in ("recordatorio_12h_enviado_at", "recordatorio_1h_enviado_at"):
        if nombre not in columnas:
            schema_editor.add_field(Trabajo, Trabajo._meta.get_field(nombre))

    if "token_confirmacion" not in columnas:
        field = Trabajo._meta.get_field("token_confirmacion")
        # Copia sin unique: el default se evalúa una sola vez, así que si se
        # crea con el unique puesto todas las filas quedan con el mismo uuid y
        # el índice falla. El unique se agrega al final, con valores por fila.
        name, path, args, kwargs = field.deconstruct()
        kwargs["unique"] = False
        columna = field.__class__(*args, **kwargs)
        columna.set_attributes_from_name(field.name)
        schema_editor.add_field(Trabajo, columna)

    if not _token_es_unico(connection, table):
        for trabajo in Trabajo.objects.all().only("id"):
            trabajo.token_confirmacion = uuid.uuid4()
            trabajo.save(update_fields=["token_confirmacion"])

        schema_editor.execute(
            f'CREATE UNIQUE INDEX IF NOT EXISTS "{UNIQUE_INDEX_NAME}" '
            f'ON "{table}" ("token_confirmacion");'
        )


class Migration(migrations.Migration):

    dependencies = [
        ("trabajos", "0011_trabajo_phonenumberinviteduser_ensure"),
    ]

    operations = [
        migrations.RunPython(ensure_trabajo_recordatorios, migrations.RunPython.noop),
    ]
