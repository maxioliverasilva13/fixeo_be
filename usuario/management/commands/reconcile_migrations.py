from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

# Reglas conocidas: esquema ya refleja la migración pero falta en django_migrations.
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
    """Inserta en django_migrations sin pasar por migrate --fake (evita InconsistentMigrationHistory)."""
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


class Command(BaseCommand):
    help = (
        "Alinea django_migrations con el esquema real cuando el historial quedó desincronizado "
        "(p. ej. contenttypes.0002 en Railway)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--record",
            nargs=2,
            metavar=("APP", "MIGRATION"),
            help="Registra una migración como aplicada vía SQL (sin checks de Django).",
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
