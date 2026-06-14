#!/bin/bash

echo "🚀 Iniciando proyecto Fixeo..."

echo "📦 Construyendo contenedores..."
docker compose up -d --build

echo "⏳ Esperando que la base de datos esté lista..."
sleep 10

echo "🔧 Activando extensiones de PostgreSQL..."
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"'

# Las migraciones deben estar en el repo; no generarlas en init (evita desalinear equipos/prod).
echo "📊 Aplicando migraciones..."
docker compose exec -T web python manage.py migrate --fake-initial

migrate_ok=0
docker compose exec -T web python manage.py migrate && migrate_ok=1 || true

if [ "$migrate_ok" -ne 1 ]; then
  echo "⚠️  migrate falló (suele pasar si la base ya tenía columnas pero no el historial en django_migrations)."
  echo "    Marcando 0002_initial como aplicadas en apps partidas y reintentando..."
  for app in carritos disponibilidad empresas localizacion mensajeria notificaciones pagos profesion rol servicios suscripciones trabajos; do
    docker compose exec -T web python manage.py migrate "$app" 0002_initial --fake 2>/dev/null || true
  done
  if ! docker compose exec -T web python manage.py migrate; then
    echo "❌ migrate sigue fallando. Revisá logs y django_migrations vs esquema real."
    exit 1
  fi
fi

echo "🌱 Ejecutando seeds..."
docker compose exec -T web python manage.py seed_roles
docker compose exec -T web python manage.py seed_profesiones
docker compose exec -T web python manage.py seed_plans
docker compose exec -T web python manage.py seed_admin

echo "✅ Proyecto iniciado correctamente!"
echo ""
echo "📝 Para crear un superusuario ejecuta:"
echo "   docker compose exec web python manage.py createsuperuser"
echo ""
echo "🌐 Accede a:"
echo "   - API: http://localhost:8000/api/"
echo "   - Admin: http://localhost:8000/admin/"
echo ""
echo "📖 Ver README.md y API_EXAMPLES.md para más información"
