#!/bin/bash

echo "🌱 Ejecutando seeds..."

echo "📝 Creando roles..."
docker-compose exec web python manage.py seed_roles

echo "📊 Creando estados..."
docker-compose exec web python manage.py seed_estados

echo "✅ Todos los seeds completados!"

