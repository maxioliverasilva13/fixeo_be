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
if docker compose exec -T web python manage.py migrate; then
  migrate_ok=1
else
  echo "⚠️  migrate falló (suele pasar si la base ya tenía columnas pero no el historial en django_migrations)."
  echo "    Recuperando: si la columna ya existe, se marca esa migración como aplicada (--fake) y se reintenta..."

  max_attempts=40
  attempt=0
  while [ "$attempt" -lt "$max_attempts" ]; do
    attempt=$((attempt + 1))
    migrate_out=""
    if migrate_out=$(docker compose exec -T web python manage.py migrate 2>&1); then
      migrate_ok=1
      break
    fi

    echo "$migrate_out"

    if echo "$migrate_out" | grep -qiE 'DuplicateColumn|DuplicateTable|already exists'; then
      failing=$(echo "$migrate_out" | grep -oE 'Applying [a-z_]+\.[0-9]+_[a-zA-Z0-9_]+' | tail -1 | sed 's/Applying //')
      if [ -z "$failing" ]; then
        break
      fi
      app="${failing%%.*}"
      mig="${failing#*.}"
      echo "    → Columna duplicada: marcando ${app}.${mig} como aplicada (--fake)..."
      if ! docker compose exec -T web python manage.py migrate "$app" "$mig" --fake; then
        break
      fi
      continue
    fi

    break
  done

  if [ "$migrate_ok" -ne 1 ] && echo "$migrate_out" | grep -qiE 'UndefinedTable|does not exist'; then
    echo ""
    echo "⚠️  La base parece inconsistente (tablas faltantes). Probablemente el fallback anterior desincronizó django_migrations."
    echo "   Solución recomendada: docker compose down -v && ./init_project.sh"
  fi
fi

if [ "$migrate_ok" -ne 1 ]; then
  echo "❌ migrate sigue fallando. Revisá logs y django_migrations vs esquema real."
  echo "   Para empezar de cero: docker compose down -v && ./init_project.sh"
  exit 1
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
