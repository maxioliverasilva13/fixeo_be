#!/bin/bash

echo "🚀 Iniciando proyecto Fixeo..."

echo "📦 Construyendo contenedores..."
docker-compose up -d --build

echo "⏳ Esperando que la base de datos esté lista..."
sleep 10

echo "🔧 Activando extensiones de PostgreSQL..."
docker compose exec db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"'

echo "🔨 Creando migraciones..."
docker-compose exec web python manage.py makemigrations


echo "📊 Aplicando migraciones..."
docker-compose exec web python manage.py migrate

echo "🌱 Ejecutando seeds..."
docker-compose exec web python manage.py seed_roles
docker-compose exec web python manage.py seed_profesiones
docker-compose exec web python manage.py seed_roles
docker-compose exec web python manage.py seed_plans

echo "✅ Proyecto iniciado correctamente!"
echo ""
echo "📝 Para crear un superusuario ejecuta:"
echo "   docker-compose exec web python manage.py createsuperuser"
echo ""
echo "🌐 Accede a:"
echo "   - API: http://localhost:8000/api/"
echo "   - Admin: http://localhost:8000/admin/"
echo ""
echo "📖 Ver README.md y API_EXAMPLES.md para más información"

