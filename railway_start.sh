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
python manage.py migrate --noinput

echo "📊 Aplicando migraciones..."
python manage.py migrate --noinput

echo "📦 Recolectando archivos estáticos..."
python manage.py collectstatic --noinput

echo "🌱 Ejecutando seeds..."
python manage.py seed_roles || echo "⚠️  Seed roles ya ejecutado o falló"
python manage.py seed_profesiones || echo "⚠️  Seed profesiones ya ejecutado o falló"
python manage.py seed_plans|| echo "⚠️  Seed profesiones ya ejecutado o falló"

echo "✅ Iniciando servidor con Gunicorn..."
gunicorn fixeo_project.wsgi:application --bind 0.0.0.0:$PORT --workers 4 --timeout 120
