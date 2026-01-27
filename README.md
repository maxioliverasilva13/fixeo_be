# Fixeo - Sistema de Gestión de Servicios

Proyecto Django con arquitectura modular, PostgreSQL, Redis y Docker.

## 🚀 Inicio Rápido

### Opción 1: Script Automático (Recomendado)

```bash
./init_project.sh
```

### Opción 2: Manual

```bash
# 1. Levantar contenedores
docker-compose up --build -d

# 2. Esperar que la BD esté lista (10-15 segundos)
sleep 10

# 3. Crear migraciones
docker-compose exec web python manage.py makemigrations
docker-compose exec web python manage.py migrate

# 4. Crear superusuario
docker-compose exec web python manage.py createsuperuser
```


## 🎯 Características Principales

### BaseModel con Auditoría Completa
Todos los modelos heredan de `BaseModel` que incluye:
- ✅ Timestamps automáticos (`created_at`, `updated_at`)
- ✅ Auditoría de usuarios (`created_by`, `updated_by`)
- ✅ Soft Delete (`is_deleted`, `deleted_at`, `deleted_by`)
- ✅ Métodos: `delete()`, `restore()`, `hard_delete()`

### Respuestas Estandarizadas
Todas las respuestas de la API siguen el formato:
```json
{
  "ok": true | false,
  "message": "Mensaje descriptivo",
  "data": { ... }
}
```

Ver `API_RESPONSE_FORMAT.md` para ejemplos completos.

## Correr proyecto de cero

# 1. Detener todo
docker-compose down -v

# 2. Levantar solo BD
docker-compose up -d db redis

# 3. Esperar
sleep 10

# 4. Crear migraciones (ahora SÍ debería detectar todas las apps)
docker-compose run --rm web python manage.py makemigrations

# 5. Aplicar migraciones
docker-compose run --rm web python manage.py migrate

# 6. Seeds
docker-compose run --rm web python manage.py seed_roles
docker-compose run --rm web python manage.py seed_estados

# 7. Levantar servidor
docker-compose up -d web