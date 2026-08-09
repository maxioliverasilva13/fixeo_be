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

echo "📊 Aplicando migraciones..."
if ! python manage.py migrate --noinput; then
  echo "⚠️  migrate falló; reintentando..."
  python manage.py migrate --noinput || echo "⚠️  migrate sigue fallando"
fi

# Safety net: columnas críticas que el código ya referencia.
# Evita UndefinedColumn si django_migrations quedó desfasado del esquema real.
python - <<'EOF'
import os
import psycopg2

conn = psycopg2.connect(os.environ["DATABASE_URL"])
conn.autocommit = True
cur = conn.cursor()
cur.execute("""
ALTER TABLE empresa
    ADD COLUMN IF NOT EXISTS tiene_landing_page boolean NOT NULL DEFAULT false;
""")
cur.close()
conn.close()
print("✓ schema ensure: empresa.tiene_landing_page")
EOF

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
