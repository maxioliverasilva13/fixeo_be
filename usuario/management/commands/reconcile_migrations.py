from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.operations.fields import AddField, AlterField, RemoveField
from django.db.migrations.operations.models import (
    AddIndex,
    CreateModel,
    DeleteModel,
    RemoveIndex,
)
from django.db.migrations.operations.special import RunPython, RunSQL, SeparateDatabaseAndState
from django.utils import timezone

PRE_MIGRATE_CHECKS = [
    {
        "app": "contenttypes",
        "name": "0002_remove_content_type_name",
        "condition_sql": """
            SELECT NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'django_content_type'
                  AND column_name = 'name'
            )
        """,
    },
]


def record_migration(app: str, name: str) -> bool:
    with connection.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM django_migrations WHERE app = %s AND name = %s",
            [app, name],
        )
        if cur.fetchone():
            return False
        cur.execute(
            "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, %s)",
            [app, name, timezone.now()],
        )
        return True


def table_exists(cur, table: str) -> bool:
    cur.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = %s
        """,
        [table],
    )
    return cur.fetchone() is not None


def column_exists(cur, table: str, column: str) -> bool:
    cur.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s AND column_name = %s
        """,
        [table, column],
    )
    return cur.fetchone() is not None


def index_exists(cur, index_name: str) -> bool:
    cur.execute(
        """
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'public' AND indexname = %s
        """,
        [index_name],
    )
    return cur.fetchone() is not None


def model_table(app_label: str, model_state) -> str:
    return model_state.options.get("db_table") or f"{app_label}_{model_state.name.lower()}"


def field_column_name(field, field_name: str) -> str:
    if getattr(field, "column", None):
        return field.column
    if getattr(field, "remote_field", None) and field.remote_field:
        return f"{field_name}_id"
    return field_name


def state_field_column(model_state, field_name: str) -> str:
    field_tuple = model_state.fields[field_name]
    internal_type = field_tuple[1].get("to") and "ForeignKey" or field_tuple[0]
    if internal_type == "ForeignKey" or field_tuple[0] in {
        "ForeignKey",
        "OneToOneField",
    }:
        return f"{field_name}_id"
    return field_name


def operation_satisfied(op, app_label: str, state_before, cur):
    if isinstance(op, SeparateDatabaseAndState):
        results = [
            operation_satisfied(db_op, app_label, state_before, cur)
            for db_op in op.database_operations
        ]
        if any(r is False for r in results):
            return False
        if all(r is True for r in results):
            return True
        return None

    if isinstance(op, AddField):
        model_key = (app_label, op.model_name.lower())
        if model_key not in state_before.models:
            return False
        model_state = state_before.models[model_key]
        table = model_table(app_label, model_state)
        column = field_column_name(op.field, op.name)
        return column_exists(cur, table, column)

    if isinstance(op, RemoveField):
        model_key = (app_label, op.model_name.lower())
        if model_key not in state_before.models:
            return False
        model_state = state_before.models[model_key]
        table = model_table(app_label, model_state)
        column = state_field_column(model_state, op.name)
        return not column_exists(cur, table, column)

    if isinstance(op, AlterField):
        model_key = (app_label, op.model_name.lower())
        if model_key not in state_before.models:
            return False
        model_state = state_before.models[model_key]
        table = model_table(app_label, model_state)
        column = field_column_name(op.field, op.name)
        return column_exists(cur, table, column)

    if isinstance(op, CreateModel):
        table = op.options.get("db_table") or f"{app_label}_{op.name.lower()}"
        return table_exists(cur, table)

    if isinstance(op, DeleteModel):
        table = op.options.get("db_table") or f"{app_label}_{op.name.lower()}"
        return not table_exists(cur, table)

    if isinstance(op, AddIndex):
        model_key = (app_label, op.model_name.lower())
        if model_key not in state_before.models:
            return False
        model_state = state_before.models[model_key]
        table = model_table(app_label, model_state)
        index_name = op.index.name or f"{table}_{'_'.join(op.index.fields)}_{'_'.join(op.index.fields)}_idx"
        if index_exists(cur, index_name):
            return True
        # Some index names differ; if table exists treat as satisfied for recovery.
        return table_exists(cur, table)

    if isinstance(op, RemoveIndex):
        return index_exists(cur, op.name) is False

    if isinstance(op, (RunPython, RunSQL)):
        return None

    return None


def migration_schema_matches(loader: MigrationLoader, app: str, name: str, cur) -> bool:
    nodes = loader.graph.forwards_plan((app, name))
    state_before = loader.project_state(nodes[:-1], at_end=True) if len(nodes) > 1 else loader.project_state([], at_end=True)
    migration = loader.get_migration(app, name)

    saw_schema_op = False
    for op in migration.operations:
        result = operation_satisfied(op, app, state_before, cur)
        if result is False:
            return False
        if result is True:
            saw_schema_op = True

    return saw_schema_op


def fix_inconsistent_history(stdout, style) -> int:
    """Registra dependencias faltantes cuando una migración aplicada las requiere."""
    fixed = 0
    with connection.cursor() as cur:
        while True:
            loader = MigrationLoader(connection)
            repaired = False

            for (app, name), migration in loader.disk_migrations.items():
                if (app, name) not in loader.applied_migrations:
                    continue
                for dep in migration.dependencies:
                    if not isinstance(dep, tuple) or len(dep) != 2:
                        continue
                    dep_app, dep_name = dep
                    if dep_name in (None, "__first__"):
                        continue
                    if (dep_app, dep_name) not in loader.graph.nodes:
                        continue
                    if (dep_app, dep_name) in loader.applied_migrations:
                        continue
                    if not migration_schema_matches(loader, dep_app, dep_name, cur):
                        continue
                    if record_migration(dep_app, dep_name):
                        stdout.write(
                            style.SUCCESS(
                                f"✓ fixed history: recorded missing dependency {dep_app}.{dep_name}"
                            )
                        )
                        fixed += 1
                        repaired = True
                        break
                if repaired:
                    break

            if not repaired:
                break

    return fixed


def auto_reconcile(stdout, style) -> int:
    recorded = 0
    with connection.cursor() as cur:
        while True:
            loader = MigrationLoader(connection)
            executor = MigrationExecutor(connection)
            plan = executor.migration_plan(loader.graph.leaf_nodes())

            first_pending = None
            for migration, backwards in plan:
                if backwards:
                    continue
                key = (migration.app_label, migration.name)
                if key not in loader.applied_migrations:
                    first_pending = migration
                    break

            if first_pending is None:
                break

            if not migration_schema_matches(
                loader, first_pending.app_label, first_pending.name, cur
            ):
                break

            if record_migration(first_pending.app_label, first_pending.name):
                stdout.write(
                    style.SUCCESS(
                        f"✓ auto-reconciled {first_pending.app_label}.{first_pending.name}"
                    )
                )
                recorded += 1
            else:
                break

    return recorded


class Command(BaseCommand):
    help = (
        "Alinea django_migrations con el esquema real cuando el historial quedó desincronizado."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--record",
            nargs=2,
            metavar=("APP", "MIGRATION"),
            help="Registra una migración como aplicada vía SQL (sin checks de Django).",
        )
        parser.add_argument(
            "--fix-history",
            action="store_true",
            help="Registra dependencias faltantes detectadas por InconsistentMigrationHistory.",
        )
        parser.add_argument(
            "--auto",
            action="store_true",
            help="Detecta migraciones cuyo esquema ya existe y las registra en bloque.",
        )

    def handle(self, *args, **options):
        record = options.get("record")
        if record:
            app, name = record
            if record_migration(app, name):
                self.stdout.write(self.style.SUCCESS(f"✓ recorded {app}.{name}"))
            else:
                self.stdout.write(f"  {app}.{name} already recorded")
            return

        if options.get("fix_history"):
            count = fix_inconsistent_history(self.stdout, self.style)
            self.stdout.write(f"  fix-history: {count} dependency migration(s) recorded")
            return

        if options.get("auto"):
            count = auto_reconcile(self.stdout, self.style)
            self.stdout.write(f"  auto-reconcile: {count} migration(s) recorded")
            return

        for rule in PRE_MIGRATE_CHECKS:
            app, name = rule["app"], rule["name"]
            with connection.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM django_migrations WHERE app = %s AND name = %s",
                    [app, name],
                )
                if cur.fetchone():
                    continue
                cur.execute(rule["condition_sql"])
                if not cur.fetchone()[0]:
                    continue

            if record_migration(app, name):
                self.stdout.write(self.style.SUCCESS(f"✓ reconciled {app}.{name}"))
