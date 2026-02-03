# Fix: Error 401 en Railway (Credenciales no proveyeron)

## Problema

Los endpoints públicos como `/api/usuarios/login/` y `/api/usuarios/registro/` devuelven error 401 en Railway pero funcionan en local.

## Causa

Cuando `DEBUG=False` (producción), Django REST Framework tiene comportamientos diferentes:
1. El middleware CSRF puede bloquear peticiones
2. Los permisos se evalúan de manera más estricta
3. CORS necesita configuración explícita

## Solución Implementada

### 1. Remover CSRF Middleware para API

Se eliminó `django.middleware.csrf.CsrfViewMiddleware` del middleware ya que es una API REST que usa JWT (no cookies de sesión).

**Antes:**
```python
MIDDLEWARE = [
    ...
    'django.middleware.csrf.CsrfViewMiddleware',  # ❌ Bloqueaba API
    ...
]
```

**Después:**
```python
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    # CSRF removido para API REST
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    ...
]
```

### 2. Configurar REST Framework

Se agregó configuración explícita de renderers:

```python
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',  # Cambiado de IsAuthenticated
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',  # Solo JSON en producción
    ],
    ...
}
```

### 3. Configurar CSRF Trusted Origins

Para el admin de Django (que sí usa CSRF):

```python
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='').split(',')
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
```

## Configuración en Railway

### Variables de Entorno Requeridas

En Railway Dashboard → Tu Servicio → Variables:

```bash
# Básicas
SECRET_KEY=tu-secret-key-super-segura-aqui
DEBUG=False
ALLOWED_HOSTS=.railway.app

# Database (Railway las mapea automáticamente)
DB_NAME=${{Postgres.PGDATABASE}}
DB_USER=${{Postgres.PGUSER}}
DB_PASSWORD=${{Postgres.PGPASSWORD}}
DB_HOST=${{Postgres.PGHOST}}
DB_PORT=${{Postgres.PGPORT}}

# Redis
REDIS_HOST=${{Redis.REDIS_HOST}}
REDIS_PORT=${{Redis.REDIS_PORT}}

# CSRF (importante!)
CSRF_TRUSTED_ORIGINS=https://tu-app.railway.app
```

### Generar SECRET_KEY Seguro

```python
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## Testing

### 1. Test Local (DEBUG=True)

```bash
# En .env local
DEBUG=True

# Probar
curl -X POST http://localhost:8000/api/usuarios/login/ \
  -H "Content-Type: application/json" \
  -d '{"correo": "test@test.com", "password": "password123"}'
```

### 2. Test Local como Producción (DEBUG=False)

```bash
# En .env local
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:8000

# Probar
curl -X POST http://localhost:8000/api/usuarios/login/ \
  -H "Content-Type: application/json" \
  -d '{"correo": "test@test.com", "password": "password123"}'
```

### 3. Test en Railway

```bash
curl -X POST https://tu-app.railway.app/api/usuarios/login/ \
  -H "Content-Type: application/json" \
  -d '{"correo": "test@test.com", "password": "password123"}'
```

## Verificación en Railway

### 1. Revisar Logs

```bash
# Con Railway CLI
railway logs

# O en Dashboard → Tu Servicio → Deployments → View Logs
```

### 2. Verificar Variables de Entorno

```bash
# Con Railway CLI
railway variables

# Verificar que estén todas las variables necesarias
```

### 3. Probar Endpoints

```bash
# Registro (público)
curl -X POST https://tu-app.railway.app/api/usuarios/registro/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123",
    "nombre": "Test",
    "apellido": "User",
    "trabajo_domicilio": true,
    "trabajo_local": false,
    "es_empresa": false,
    "profesion_ids": []
  }'

# Login (público)
curl -X POST https://tu-app.railway.app/api/usuarios/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "correo": "test@example.com",
    "password": "password123"
  }'

# Me (protegido - debe fallar sin token)
curl https://tu-app.railway.app/api/usuarios/me/

# Me (protegido - debe funcionar con token)
curl https://tu-app.railway.app/api/usuarios/me/ \
  -H "Authorization: Bearer TU_ACCESS_TOKEN"
```

## Troubleshooting

### Error: "CSRF verification failed"

**Solución:** Agregar tu dominio a `CSRF_TRUSTED_ORIGINS`:

```bash
# En Railway
CSRF_TRUSTED_ORIGINS=https://tu-app.railway.app,https://tu-dominio-custom.com
```

### Error: "Invalid HTTP_HOST header"

**Solución:** Actualizar `ALLOWED_HOSTS`:

```bash
# En Railway
ALLOWED_HOSTS=.railway.app,tu-dominio-custom.com
```

### Error: "Authentication credentials were not provided"

**Causas posibles:**
1. ❌ `DEFAULT_PERMISSION_CLASSES` sigue en `IsAuthenticated`
2. ❌ El ViewSet no tiene `permission_classes=[AllowAny]` en el método
3. ❌ Middleware está bloqueando la petición

**Verificar:**
```python
# En settings.py
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',  # ✅ Debe ser AllowAny
    ],
}

# En views.py
@action(detail=False, methods=['post'], permission_classes=[AllowAny])
def login(self, request):
    ...
```

### Error: CORS

**Solución:** Verificar configuración CORS:

```python
# En settings.py
if DEBUG:
    CORS_ALLOWED_ORIGINS = [...]
else:
    CORS_ALLOW_ALL_ORIGINS = True  # Para desarrollo
    # O especificar dominios:
    # CORS_ALLOWED_ORIGINS = ['https://tu-frontend.com']
```

## Checklist de Deploy

Antes de hacer deploy a Railway:

- [x] Remover CSRF middleware de `MIDDLEWARE`
- [x] Cambiar `DEFAULT_PERMISSION_CLASSES` a `AllowAny`
- [x] Agregar `DEFAULT_RENDERER_CLASSES` con `JSONRenderer`
- [x] Configurar `CSRF_TRUSTED_ORIGINS`
- [ ] Generar `SECRET_KEY` seguro en Railway
- [ ] Configurar todas las variables de entorno en Railway
- [ ] Agregar dominio de Railway a `CSRF_TRUSTED_ORIGINS`
- [ ] Verificar que `DEBUG=False` en Railway
- [ ] Probar endpoints públicos (login, registro)
- [ ] Probar endpoints protegidos con token

## Comandos Útiles

```bash
# Ver logs en tiempo real
railway logs --follow

# Ejecutar comando en Railway
railway run python manage.py showmigrations

# Conectar a la base de datos
railway run python manage.py dbshell

# Crear superusuario
railway run python manage.py createsuperuser

# Ver variables de entorno
railway variables
```

## Notas Importantes

1. **CSRF solo para Admin:** El admin de Django (`/admin/`) sigue usando CSRF, pero la API REST no lo necesita porque usa JWT.

2. **CORS en Producción:** Considera especificar dominios exactos en lugar de `CORS_ALLOW_ALL_ORIGINS = True` para mayor seguridad.

3. **HTTPS:** Railway proporciona HTTPS automáticamente, por eso `CSRF_COOKIE_SECURE` y `SESSION_COOKIE_SECURE` están en `True` cuando `DEBUG=False`.

4. **Logs:** Siempre revisa los logs en Railway para ver errores específicos.

## Referencias

- [Django REST Framework Authentication](https://www.django-rest-framework.org/api-guide/authentication/)
- [Django CSRF Documentation](https://docs.djangoproject.com/en/5.0/ref/csrf/)
- [Railway Docs](https://docs.railway.app/)
