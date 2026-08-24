from pathlib import Path
from decouple import config
import json

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = [h.strip() for h in config('ALLOWED_HOSTS', default='localhost').split(',') if h.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.postgres',
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_filters',
    'usuario',
    'rol',
    'profesion',
    'disponibilidad',
    'usuario_profesion',
    'usuario_localizacion',
    'localizacion',
    'empresas',
    'carritos',
    'trabajos',
    'mensajeria',
    'notificaciones',
    'publicidades',
    'suscripciones',
    'recursos',
    'servicios',
    'horarios',
    'pagos',
    'whatsapp',
    'moderacion',
    'rest_framework_simplejwt.token_blacklist',
    'channels',
    'survey'
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'fixeo_project.middleware.CurrentUserMiddleware',
    'fixeo_project.transaction_middleware.ConditionalAtomicRequestsMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'fixeo_project.response_middleware.StandardizedResponseMiddleware',
]

ROOT_URLCONF = 'fixeo_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'fixeo_project.wsgi.application'
ASGI_APPLICATION = 'fixeo_project.asgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST'),
        'PORT': config('DB_PORT'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es-ar'
TIME_ZONE = 'America/Montevideo'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# WhiteNoise configuration for production
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'usuario.Usuario'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'usuario.authentication.SlidingJWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}

from datetime import timedelta

JWT_INACTIVITY_DAYS = 30

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=JWT_INACTIVITY_DAYS),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=JWT_INACTIVITY_DAYS),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
}

# CORS — landing (subdominios), app móvil/web y desarrollo local
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https?://([\w-]+\.)?localhost(:\d+)?$",
    r"^https?://([\w-]+\.)?alavueltaapp\.com(:\d+)?$",
    r"^https?://([\w-]+\.)?alavueltaapp\.pro(:\d+)?$",
    r"^https?://127\.0\.0\.1(:\d+)?$",
    r"^https?://172\.20\.10\.\d+(:\d+)?$",
    r"^https?://192\.168\.\d+\.\d+(:\d+)?$",
    r"^https?://10\.\d+\.\d+\.\d+(:\d+)?$",
]

if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
    
else:
    CORS_ALLOW_ALL_ORIGINS = True

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'ngrok-skip-browser-warning',
]
# Métodos HTTP permitidos
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

# CSRF Settings for API
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='').split(',') if config('CSRF_TRUSTED_ORIGINS', default='') else []
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG

REDIS_URL = config('REDIS_URL', default=None)
if REDIS_URL:
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
else:
    REDIS_HOST = config('REDIS_HOST', default='localhost')
    REDIS_PORT = config('REDIS_PORT', default='6379')
    REDIS_PASSWORD = config('REDIS_PASSWORD', default=None)
    
    if REDIS_PASSWORD:
        CELERY_BROKER_URL = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0"
        CELERY_RESULT_BACKEND = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0"
    else:
        CELERY_BROKER_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
        CELERY_RESULT_BACKEND = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [CELERY_BROKER_URL],
        },
    },
}

CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'America/Montevideo'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
# Si Redis está caído, fallar rápido en vez de colgar el request HTTP ~20s.
CELERY_BROKER_TRANSPORT_OPTIONS = {
    'socket_timeout': 2,
    'socket_connect_timeout': 2,
    'retry_on_timeout': False,
}
CELERY_RESULT_BACKEND_TRANSPORT_OPTIONS = {
    'socket_timeout': 2,
    'socket_connect_timeout': 2,
    'retry_on_timeout': False,
}
CELERY_TASK_IGNORE_RESULT = True
CELERY_IMPORTS = (
    'trabajos.tasks',
    'notificaciones.tasks',
    'whatsapp.tasks',
    'fixeo_project.tasks',
)

FINALIZACION_TRABAJO_DESPUES_DE_MINUTES = config(
    'FINALIZACION_TRABAJO_DESPUES_DE_MINUTES',
    default=1,
    cast=int,
)
RECORDATORIO_CALIFICAR_PROFESIONAL_TRABAJO_MINUTES = config(
    'RECORDATORIO_CALIFICAR_PROFESIONAL_TRABAJO_MINUTES',
    default=1,
    cast=int,
)
CELERY_FINALIZAR_TRABAJOS_INTERVAL_SECONDS = config(
    'CELERY_FINALIZAR_TRABAJOS_INTERVAL_SECONDS',
    default=60,
    cast=float,
)
CELERY_BEAT_SCHEDULE = {
    'finalizar-trabajos-vencidos': {
        'task': 'trabajos.finalizar_trabajos_vencidos',
        'schedule': CELERY_FINALIZAR_TRABAJOS_INTERVAL_SECONDS,
    },
}

FIREBASE_CREDENTIALS = config('FIREBASE_CREDENTIALS', default=None)

RESEND_API_KEY = config('RESEND_API_KEY', default='')

# Google Gemini (visión) para análisis de imágenes de productos
GEMINI_API_KEY = config('GEMINI_API_KEY', default='')
GEMINI_MODEL = config('GEMINI_MODEL', default='gemini-3.6-flash')

FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:8081')
EMAIL_FROM = config('EMAIL_FROM', default='onboarding@resend.dev')
EMAIL_LOGO_URL = config('EMAIL_LOGO_URL', default='')

import logging
logger = logging.getLogger(__name__)
# MercadoPago
MP_ACCESS_TOKEN = config('MP_ACCESS_TOKEN', default='')
MP_PUBLIC_KEY = config('MP_PUBLIC_KEY', default='')
MP_APP_ID = config('MP_APP_ID', default='')
MP_APP_SECRET = config('MP_APP_SECRET', default='')
MP_APP_SCHEME = config('MP_APP_SCHEME', default='com.alavueltaapp')
MP_OAUTH_URL = config('MP_OAUTH_URL', default='https://auth.mercadopago.com.uy/authorization')
PLATFORM_COMMISSION_PERCENT = config('PLATFORM_COMMISSION_PERCENT', default=10, cast=int)
MP_WEBHOOK_BASE_URL = config('MP_WEBHOOK_BASE_URL', default='http://localhost:8000')
MP_WEBHOOK_SECRET = config('MP_WEBHOOK_SECRET', default='')
MP_TEST_MODE = config('MP_TEST_MODE', default=False, cast=bool)

if FIREBASE_CREDENTIALS:
    from fixeo_project.firebase_init import ensure_firebase_app

    ensure_firebase_app(FIREBASE_CREDENTIALS)


# ---------------------------------------------------------------------------
# In-App Purchases (Google Play + Apple App Store)
# ---------------------------------------------------------------------------
# Todas las variables son opcionales: si no están seteadas, los servicios se
# inicializan en modo "no configurado" y la app sigue arrancando normal.
# Solo los endpoints específicos devolverán un mensaje claro cuando se llamen.
GOOGLE_SERVICE_ACCOUNT_KEY = config('GOOGLE_SERVICE_ACCOUNT_KEY', default='')
GOOGLE_PLAY_PACKAGE_NAME = config('GOOGLE_PLAY_PACKAGE_NAME', default='')

APP_STORE_SHARED_SECRET = config('APP_STORE_SHARED_SECRET', default='')
APP_STORE_ENVIRONMENT = config('APP_STORE_ENVIRONMENT', default='sandbox')
APP_STORE_KEY_ID = config('APP_STORE_KEY_ID', default='')
APP_STORE_ISSUER_ID = config('APP_STORE_ISSUER_ID', default='')
APP_STORE_BUNDLE_ID = config('APP_STORE_BUNDLE_ID', default='com.alavueltaapp')
APP_STORE_API_KEY = config('APP_STORE_API_KEY', default='')


# ---------------------------------------------------------------------------
# WhatsApp (Meta Cloud API)
# ---------------------------------------------------------------------------
WHATSAPP_ACCESS_TOKEN = config('WHATSAPP_ACCESS_TOKEN', default='')
WHATSAPP_PHONE_NUMBER_ID = config('WHATSAPP_PHONE_NUMBER_ID', default='')
WHATSAPP_BUSINESS_ACCOUNT_ID = config('WHATSAPP_BUSINESS_ACCOUNT_ID', default='')
WHATSAPP_API_VERSION = config('WHATSAPP_API_VERSION', default='v20.0')
WHATSAPP_GRAPH_BASE_URL = config('WHATSAPP_GRAPH_BASE_URL', default='https://graph.facebook.com')
WHATSAPP_WEBHOOK_TOKEN = config('WHATSAPP_WEBHOOK_TOKEN', default='')
WHATSAPP_APP_SECRET = config('WHATSAPP_APP_SECRET', default='')
# Usuario.telefono se guarda sin código de país (el matching de mensajes entrantes
# usa los últimos 8 dígitos). Al enviar, si el número no trae código de país se le
# antepone este default.
WHATSAPP_DEFAULT_COUNTRY_CODE = config('WHATSAPP_DEFAULT_COUNTRY_CODE', default='598')

