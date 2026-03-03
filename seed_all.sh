#!/bin/bash

echo "🌱 Ejecutando seeds..."

echo "📝 Creando roles..."
docker-compose exec web python manage.py seed_roles
docker-compose exec web python manage.py seed_plans

echo "✅ Todos los seeds completados!"

