#!/bin/bash

echo "🔄 Iniciando Celery Worker con Beat..."

# Ejecutar worker con beat (tareas periódicas)
exec celery -A fixeo_project worker --beat --loglevel=info --concurrency=4
