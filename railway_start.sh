#!/bin/bash

echo "🚀 Iniciando aplicación en Railway..."

echo "📊 Aplicando migraciones..."
python manage.py migrate --noinput

echo "📦 Recolectando archivos estáticos..."
python manage.py collectstatic --noinput

echo "🌱 Ejecutando seeds..."
python manage.py seed_roles || echo "⚠️  Seed roles ya ejecutado o falló"
python manage.py seed_profesiones || echo "⚠️  Seed profesiones ya ejecutado o falló"

echo "✅ Iniciando servidor con Gunicorn..."
gunicorn fixeo_project.wsgi:application --bind 0.0.0.0:$PORT --workers 4 --timeout 120
