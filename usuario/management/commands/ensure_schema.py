from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.operations.models import (
    AlterModelTable,
    CreateModel,
    RenameModel,
)
from django.db.migrations.operations.special import SeparateDatabaseAndState


def _create_model_tables(loader):
    """Tablas que crearían (o renombrarían) las migraciones TODAVÍA no aplicadas.

    Si una tabla falta y una migración pendiente la crea o la renombra, no hay
    que tocarla: `migrate` la va a dejar como corresponde. Este comando sólo
    repara el caso de migraciones que quedaron registradas en django_migrations
    sin ejecutar su DDL.
    """
    tables = set()
    for (app_label, name), migration in loader.disk_migrations.items():
        if (app_label, name) in loader.applied_migrations:
            continue
        create_ops = []
        alter_table_ops = []
        for op in migration.operations:
            candidates = [op]
            if isinstance(op, SeparateDatabaseAndState):
                candidates = list(op.state_operations) + list(op.database_operations)
            for candidate in candidates:
                if isinstance(candidate, CreateModel):
                    create_ops.append(candidate)
                elif isinstance(candidate, AlterModelTable):
                    alter_table_ops.append(candidate)
        for op in create_ops:
            tables.add(op.options.get("db_table") or f"{app_label}_{op.name.lower()}")
        for op in alter_table_ops:
            # table=None significa "volver al nombre por defecto" (db_table del modelo).
            tables.add(op.table or f"{app_label}_{op.name.lower()}")
    return tables


class Command(BaseCommand):
    """Crea tablas que el estado final de migraciones espera y la base no tiene.

    Es la red de seguridad para migraciones "fakeadas" (registradas en
    django_migrations sin DDL). El DDL lo genera Django con schema_editor, así
    que tipos, identidades, FKs e índices quedan iguales a los de la migración.
    Por defecto sólo informa; con --apply repara.
    """

    help = "Crea tablas faltantes cuyo DDL no ejecutó una migración ya registrada como aplicada."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Crea las tablas faltantes (sin este flag sólo se reportan).",
        )

    def handle(self, *args, **options):
        loader = MigrationLoader(connection)
        state = loader.project_state()
        pending_tables = _create_model_tables(loader)

        with connection.cursor() as cur:
            db_tables = {info.name for info in connection.introspection.get_table_list(cur)}

        missing = []
        skipped_pending = []
        for model in state.apps.get_models():
            meta = model._meta
            if meta.proxy or not meta.managed or meta.auto_created:
                continue
            if meta.db_table in db_tables:
                continue
            if meta.db_table in pending_tables:
                skipped_pending.append(meta.db_table)
                self.stdout.write(
                    f"  · {meta.db_table}: falta, la crea una migración pendiente (no se toca)"
                )
                continue
            missing.append(model)

        if not missing:
            if skipped_pending:
                muestra = ", ".join(skipped_pending[:5])
                if len(skipped_pending) > 5:
                    muestra += f" ... (+{len(skipped_pending) - 5})"
                self.stdout.write(
                    self.style.WARNING(
                        f"  {len(skipped_pending)} tabla(s) faltante(s) las tiene que crear "
                        f"`migrate` (hay migraciones pendientes): {muestra}"
                    )
                )
            else:
                self.stdout.write(self.style.SUCCESS("✓ no falta ninguna tabla"))
            return

        for model in missing:
            self.stdout.write(self.style.WARNING(f"✗ falta la tabla {model._meta.db_table}"))

        if not options["apply"]:
            self.stdout.write("  (modo informe: usá --apply para crearlas)")
            return

        known = set(db_tables)
        pending = list(missing)
        failed = []
        while pending:
            progressed = False
            for model in list(pending):
                meta = model._meta
                targets = set()
                for field in meta.local_fields:
                    if not field.is_relation or field.remote_field is None:
                        continue
                    target = field.remote_field.model
                    if target is None:
                        continue
                    table = target._meta.db_table
                    if table != meta.db_table:
                        targets.add(table)
                if not targets <= known:
                    continue

                try:
                    with connection.schema_editor() as editor:
                        editor.create_model(model)
                    known.add(meta.db_table)
                    self.stdout.write(self.style.SUCCESS(f"✓ creada la tabla {meta.db_table}"))
                except Exception as exc:  # noqa: BLE001 - se reporta y se sigue
                    known.add(meta.db_table)
                    failed.append(meta.db_table)
                    self.stderr.write(
                        self.style.ERROR(f"✗ no se pudo crear {meta.db_table}: {exc}")
                    )
                pending.remove(model)
                progressed = True

            if not progressed:
                for model in pending:
                    failed.append(model._meta.db_table)
                    self.stderr.write(
                        self.style.ERROR(
                            f"✗ {model._meta.db_table}: no se pudo crear "
                            "(depende de otra tabla que tampoco se pudo crear)"
                        )
                    )
                break

        if failed:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠️  quedaron {len(failed)} tabla(s) sin crear: {', '.join(failed)}. "
                    "Revisá el error y corré la migración correspondiente."
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("✓ tablas faltantes reparadas"))
