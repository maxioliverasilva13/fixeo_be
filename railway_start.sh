#!/bin/bash

echo "🚀 Iniciando aplicación en Railway..."

echo "🔧 Activando extensión pg_trgm..."

python - <<EOF
import psycopg2, os

conn = psycopg2.connect(os.environ["DATABASE_URL"])
conn.autocommit = True
cur = conn.cursor()

cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

cur.close()
conn.close()
EOF

echo "📊 Reconciliando historial de migraciones..."
python manage.py reconcile_migrations || echo "⚠️  reconcile_migrations falló (continúo)"

echo "📊 Aplicando migraciones..."
migrate_ok=0
max_rounds=50
round=0
while [ "$round" -lt "$max_rounds" ]; do
  round=$((round + 1))
  python manage.py reconcile_migrations --auto || true

  migrate_out=""
  if migrate_out=$(python manage.py migrate --noinput 2>&1); then
    echo "$migrate_out"
    migrate_ok=1
    break
  fi

  echo "$migrate_out"

  if echo "$migrate_out" | grep -qi 'InconsistentMigrationHistory'; then
    dep=$(echo "$migrate_out" | grep -oE 'dependency [a-z_]+\.[0-9]+_[a-zA-Z0-9_]+' | head -1 | sed 's/dependency //')
    if [ -n "$dep" ]; then
      app="${dep%%.*}"
      mig="${dep#*.}"
      echo "    → Dependencia faltante: registrando ${app}.${mig}..."
      python manage.py reconcile_migrations --record "$app" "$mig" || break
      continue
    fi
    python manage.py reconcile_migrations --fix-history || true
    continue
  fi

  if echo "$migrate_out" | grep -qiE 'DuplicateColumn|DuplicateTable|already exists|UndefinedColumn|UndefinedTable|does not exist'; then
    failing=$(echo "$migrate_out" | grep -oE 'Applying [a-z_]+\.[0-9]+_[a-zA-Z0-9_]+' | tail -1 | sed 's/Applying //')
    if [ -n "$failing" ]; then
      app="${failing%%.*}"
      mig="${failing#*.}"
      # Sólo se registra si el esquema de esa migración YA existe.
      # Un "column ... does not exist" de un AddField NO se puede registrar:
      # quedaba como aplicada sin crear la columna y la API devolvía 500 para siempre.
      echo "    → Verificando si ${app}.${mig} ya está aplicada en el esquema..."
      python manage.py reconcile_migrations --record-if-satisfied "$app" "$mig" || break
      continue
    fi
  fi

  break
done

if [ "$migrate_ok" -ne 1 ]; then
  # Un error en una migración (p. ej. un RunPython que revienta) aborta el plan
  # completo y deja SIN aplicar todo lo que viene después alfabéticamente
  # (caso real: token_blacklist.0003 rompía y bloqueaba trabajos/usuario/whatsapp).
  # Se reintenta app por app para que un problema no arrastre al resto.
  echo "⚠️  migrate global falló; reintentando app por app..."
  python manage.py reconcile_migrations --auto || true

  pending_apps=$(python - <<'PY'
import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fixeo_project.settings')
django.setup()

from django.db import connection  # noqa: E402
from django.db.migrations.loader import MigrationLoader  # noqa: E402

loader = MigrationLoader(connection)
print(' '.join(sorted({app for app, _ in loader.disk_migrations})))
PY
)

  for app in $pending_apps; do
    applied=0
    # Hasta 5 vueltas por app: si falla con "ya existe", el DDL está aplicado
    # pero falta la fila en django_migrations → se registra y se sigue.
    for _ in 1 2 3 4 5; do
      if app_out=$(python manage.py migrate "$app" --noinput 2>&1); then
        applied=$(echo "$app_out" | grep -c "Applying ")
        break
      fi
      echo "$app_out" | grep -qiE 'DuplicateColumn|DuplicateTable|already exists' || break
      failing=$(echo "$app_out" | grep -oE 'Applying [a-z_]+\.[0-9]+_[a-zA-Z0-9_]+' | tail -1 | sed 's/Applying //')
      [ -n "$failing" ] || break
      failing_app="${failing%%.*}"
      failing_mig="${failing#*.}"
      echo "    → ${failing_app}.${failing_mig}: el DDL ya existe, registrando en django_migrations"
      python manage.py reconcile_migrations --record-if-satisfied "$failing_app" "$failing_mig" || break
    done
    if [ "$applied" -gt 0 ]; then
      echo "  ✓ ${app}: ${applied} migración(es) aplicadas"
    fi
  done
fi

# Safety net: columnas críticas que el código ya referencia y que pueden faltar
# si `migrate` quedó a medias (migración registrada sin ejecutar su DDL).
# Los ALTER son idempotentes (ADD COLUMN IF NOT EXISTS).
python - <<'EOF'
import os
import psycopg2

# (tabla, columna, definición SQL)
EXPECTED_COLUMNS = [
    ("empresa", "tiene_landing_page", "boolean NOT NULL DEFAULT false"),
    ("usuario", "activar_agente", "boolean NOT NULL DEFAULT false"),
    ("orden", '"phoneNumberInvitedUser"', "varchar(32) NOT NULL DEFAULT ''"),
    ("trabajo", '"phoneNumberInvitedUser"', "varchar(32) NOT NULL DEFAULT ''"),
]

conn = psycopg2.connect(os.environ["DATABASE_URL"])
conn.autocommit = True
cur = conn.cursor()

repaired = []
for table, column, ddl in EXPECTED_COLUMNS:
    cur.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s AND column_name = %s
        """,
        [table, column.strip('"')],
    )
    if cur.fetchone():
        continue
    try:
        cur.execute(f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS {column} {ddl};')
        repaired.append(f"{table}.{column}")
    except Exception as exc:
        print(f"  ✗ no se pudo crear {table}.{column}: {exc}")

cur.close()
conn.close()

if repaired:
    print(f"✓ schema ensure: reparadas columnas {', '.join(repaired)}")
else:
    print("✓ schema ensure: columnas críticas OK")
EOF

# Red de seguridad: tablas que una migración registrada nunca creó (caso
# whatsapp.0002 → "relation whatsapp_conversacionwhatsapp does not exist").
# El DDL lo genera Django (tipos, FK, unique), no SQL a mano.
echo "🧩 Reparando tablas faltantes..."
python manage.py ensure_schema --apply || echo "⚠️  ensure_schema no pudo ejecutarse"

# Diagnóstico (solo lectura): si algo falta, queda en el log en vez de aparecer
# como 500 "column ... does not exist" en cada request.
echo "🔎 Verificando esquema contra el estado final de migraciones..."
python manage.py check_schema || echo "⚠️  check_schema no pudo ejecutarse"

echo "📦 Recolectando archivos estáticos..."
python manage.py collectstatic --noinput

echo "🌱 Ejecutando seeds..."
python manage.py seed_roles || echo "⚠️  Seed roles ya ejecutado o falló"
python manage.py seed_profesiones || echo "⚠️  Seed profesiones ya ejecutado o falló"
python manage.py seed_plans || echo "⚠️  Seed planes ya ejecutado o falló"
python manage.py seed_admin || echo "⚠️  Seed admin ya ejecutado o falló"

# Admin de panel (idempotente)
python - <<'EOF'
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fixeo_project.settings')
django.setup()
from django.contrib.auth.hashers import make_password
from usuario.models import Usuario
from rol.models import Rol

rol, _ = Rol.objects.get_or_create(nombre='admin')
user, created = Usuario.objects.get_or_create(
    correo='admin@gmail.com',
    defaults={
        'nombre': 'Admin',
        'apellido': 'Sistema',
        'telefono': '',
        'is_staff': True,
        'is_superuser': True,
        'is_active': True,
        'is_owner_empresa': False,
        'rol': rol,
        'password': make_password('admin1234'),
    },
)
if not created:
    user.is_staff = True
    user.is_superuser = True
    user.is_active = True
    user.rol = rol
    user.save(update_fields=['is_staff', 'is_superuser', 'is_active', 'rol'])
print(f"✓ admin panel: {user.correo} ({'created' if created else 'exists'})")
EOF

echo "✅ Iniciando servidor con Daphne (ASGI + WebSockets)..."
daphne -b 0.0.0.0 -p $PORT fixeo_project.asgi:application
