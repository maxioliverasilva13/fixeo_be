from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.loader import MigrationLoader


class Command(BaseCommand):
    """Compara el estado final de las migraciones con el esquema real (solo lectura).

    Sirve para detectar bases donde alguna migración quedó registrada en
    django_migrations (por `reconcile_migrations --record`) pero su DDL nunca se
    ejecutó: ahí el código referencia columnas/tablas que no existen y la API
    devuelve 500 ("column ... does not exist").
    """

    help = "Reporta tablas/columnas que el estado final de migraciones espera y la base no tiene."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fail-on-drift",
            action="store_true",
            help="Sale con código 1 si encuentra diferencias (para CI / verificación manual).",
        )

    def handle(self, *args, **options):
        loader = MigrationLoader(connection)
        state = loader.project_state()

        # (tabla, columna o None, origen) tal como lo define el estado de migraciones.
        expected = []
        for model in state.apps.get_models(include_auto_created=True, include_swapped=True):
            meta = model._meta
            if meta.proxy or not meta.managed:
                continue
            origin = f"{meta.app_label}.{meta.object_name}"
            expected.append((meta.db_table, None, origin))
            for field in meta.local_fields:
                if field.column:
                    expected.append((meta.db_table, field.column, f"{origin}.{field.name}"))

        with connection.cursor() as cur:
            db_tables = {info.name for info in connection.introspection.get_table_list(cur)}
            db_columns = {}
            for table in {table for table, _, _ in expected}:
                if table not in db_tables:
                    continue
                with connection.cursor() as cur:
                    db_columns[table] = {
                        info.name
                        for info in connection.introspection.get_table_description(cur, table)
                    }

        missing_tables = []
        missing_columns = []
        seen_tables = set()
        for table, column, origin in expected:
            if table not in db_tables:
                if table not in seen_tables:
                    seen_tables.add(table)
                    missing_tables.append((table, origin))
                continue
            if column is None:
                continue
            if column not in db_columns.get(table, set()):
                missing_columns.append((table, column, origin))

        for table, origin in missing_tables:
            self.stdout.write(self.style.ERROR(f"✗ falta la tabla {table} ({origin})"))
        for table, column, origin in missing_columns:
            self.stdout.write(self.style.ERROR(f"✗ falta la columna {table}.{column} ({origin})"))

        total = len(missing_tables) + len(missing_columns)
        if total:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠️  {total} objeto(s) que el código espera no existen en la base. "
                    "Suele venir de una migración registrada como aplicada sin ejecutar su DDL: "
                    "revisá `python manage.py showmigrations` y corré `python manage.py migrate`."
                )
            )
            if options["fail_on_drift"]:
                raise SystemExit(1)
        else:
            self.stdout.write(self.style.SUCCESS("✓ esquema alineado con las migraciones"))
