# Guía de Deployment en Railway

Esta guía te ayudará a deployar el backend de Fixeo en Railway.

## 📋 Prerequisitos

1. Cuenta en [Railway](https://railway.app/)
2. Repositorio Git del proyecto
3. CLI de Railway (opcional): `npm i -g @railway/cli`

## 🚀 Pasos para el Deployment

### 1. Crear Proyecto en Railway

1. Ve a [Railway Dashboard](https://railway.app/dashboard)
2. Click en "New Project"
3. Selecciona "Deploy from GitHub repo"
4. Autoriza Railway a acceder a tu repositorio
5. Selecciona el repositorio de Fixeo

### 2. Agregar PostgreSQL

1. En tu proyecto de Railway, click en "+ New"
2. Selecciona "Database" → "Add PostgreSQL"
3. Railway creará automáticamente las variables de entorno:
   - `PGHOST`
   - `PGPORT`
   - `PGUSER`
   - `PGPASSWORD`
   - `PGDATABASE`

### 3. Agregar Redis

1. Click en "+ New"
2. Selecciona "Database" → "Add Redis"
3. Railway creará automáticamente las variables de entorno:
   - `REDIS_URL`
   - `REDIS_HOST`
   - `REDIS_PORT`

### 4. Configurar Variables de Entorno

En el servicio web (tu aplicación Django), agrega las siguientes variables:

```bash
# Django
SECRET_KEY=tu-secret-key-super-segura-aqui
DEBUG=False
ALLOWED_HOSTS=.railway.app

# Database (Railway las mapea automáticamente, pero usa estos nombres)
DB_NAME=${{Postgres.PGDATABASE}}
DB_USER=${{Postgres.PGUSER}}
DB_PASSWORD=${{Postgres.PGPASSWORD}}
DB_HOST=${{Postgres.PGHOST}}
DB_PORT=${{Postgres.PGPORT}}

# Redis
REDIS_HOST=${{Redis.REDIS_HOST}}
REDIS_PORT=${{Redis.REDIS_PORT}}

# Opcional: Supabase
SUPABASE_URL=tu-supabase-url
SUPABASE_KEY=tu-supabase-key
```

**Nota:** Railway permite referenciar variables de otros servicios usando la sintaxis `${{ServiceName.VARIABLE}}`

### 5. Configurar el Build

Railway detectará automáticamente el `Dockerfile` y `railway.json`. No necesitas configuración adicional.

### 6. Deploy

1. Railway iniciará el build automáticamente
2. Espera a que termine el proceso (puede tomar 3-5 minutos)
3. Una vez completado, Railway te dará una URL pública

### 7. Generar un Dominio

1. Ve a "Settings" en tu servicio web
2. En "Networking" → "Public Networking"
3. Click en "Generate Domain"
4. Railway te dará un dominio como: `fixeo-production.up.railway.app`

### 8. Crear Superusuario (Opcional)

Puedes crear un superusuario usando la CLI de Railway:

```bash
railway login
railway link
railway run python manage.py createsuperuser
```

O desde el dashboard:
1. Ve a tu servicio web
2. Click en "Deploy Logs"
3. Usa el terminal interactivo si está disponible

## 🔧 Archivos Importantes

- **`railway.json`**: Configuración de Railway
- **`railway_start.sh`**: Script de inicio que ejecuta migraciones y seeds
- **`Dockerfile.railway`**: Dockerfile optimizado para Railway
- **`requirements.txt`**: Incluye `gunicorn` y `whitenoise` para producción

## 📝 Comandos Útiles con Railway CLI

```bash
# Login
railway login

# Vincular proyecto
railway link

# Ver logs
railway logs

# Ejecutar comandos
railway run python manage.py migrate
railway run python manage.py createsuperuser

# Variables de entorno
railway variables

# Abrir en navegador
railway open
```

## 🔍 Troubleshooting

### Error: "Application failed to respond"
- Verifica que Gunicorn esté instalado: `pip install gunicorn`
- Revisa los logs en Railway Dashboard
- Asegúrate de que `PORT` esté configurado correctamente (Railway lo hace automático)

### Error de Base de Datos
- Verifica que las variables de entorno estén correctamente mapeadas
- Asegúrate de que PostgreSQL esté corriendo
- Revisa la conexión: `railway run python manage.py dbshell`

### Error en Migraciones
- Ejecuta manualmente: `railway run python manage.py migrate`
- Verifica que todas las apps estén en `INSTALLED_APPS`

### Error 500 en Producción
- Activa temporalmente `DEBUG=True` para ver el error
- Revisa los logs: `railway logs`
- Verifica `ALLOWED_HOSTS`

## 🌐 URLs del Proyecto

Una vez deployado, tendrás acceso a:

- **API**: `https://tu-dominio.railway.app/api/`
- **Admin**: `https://tu-dominio.railway.app/admin/`
- **Health Check**: `https://tu-dominio.railway.app/` (si lo configuras)

## 📊 Monitoreo

Railway proporciona:
- Logs en tiempo real
- Métricas de CPU y memoria
- Reinicio automático en caso de fallos
- Rollback a versiones anteriores

## 💰 Costos

Railway ofrece:
- **Plan Hobby**: $5/mes + uso
- **Plan Pro**: $20/mes + uso
- Crédito inicial de $5 para probar

Los recursos se cobran por uso:
- PostgreSQL: ~$5-10/mes
- Redis: ~$2-5/mes
- Web Service: Según CPU/RAM

## 🔐 Seguridad

1. **Nunca** commits el archivo `.env`
2. Usa variables de entorno en Railway
3. Genera un `SECRET_KEY` seguro:
   ```python
   from django.core.management.utils import get_random_secret_key
   print(get_random_secret_key())
   ```
4. Mantén `DEBUG=False` en producción
5. Configura `ALLOWED_HOSTS` correctamente

## 📚 Recursos

- [Railway Docs](https://docs.railway.app/)
- [Django Deployment Checklist](https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/)
- [Gunicorn Docs](https://docs.gunicorn.org/)
- [WhiteNoise Docs](http://whitenoise.evans.io/)

## 🆘 Soporte

Si tienes problemas:
1. Revisa los logs en Railway Dashboard
2. Consulta la [Railway Community](https://discord.gg/railway)
3. Revisa este README y la documentación oficial
