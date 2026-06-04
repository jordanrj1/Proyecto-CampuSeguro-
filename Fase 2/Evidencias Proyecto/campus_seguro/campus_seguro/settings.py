# ═══════════════════════════════════════════════════════════════
# CAMPUS SEGURO – Configuración Django
# ─────────────────────────────────────────────────────────────
# Archivo: campus_seguro/settings.py
# Propósito: Configuración central del proyecto. Lee valores sensibles
#            desde variables de entorno (.env) usando python-dotenv.
#
# VARIABLES DE ENTORNO REQUERIDAS:
#   Ver .env.example para la lista completa.
#   Ver docs/AUTH0_CONFIGURACION.md para instrucciones de Auth0.
#
# CONEXIONES:
#   - Lee: .env (variables de entorno locales)
#   - Usado por: todos los módulos Django, auth0_service.py
# ═══════════════════════════════════════════════════════════════
import os
from pathlib import Path

# Carga las variables del archivo .env al entorno de Python.
# Si .env no existe, usa las variables de sistema (comportamiento
# estándar en servidores de producción con variables configuradas
# directamente en el entorno del proceso).
from dotenv import load_dotenv
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Seguridad ────────────────────────────────────────────────
# SECRET_KEY: leído desde .env para no tener claves en el código fuente.
# En desarrollo usa el valor por defecto si .env no tiene el valor.
SECRET_KEY = os.getenv(
    'DJANGO_SECRET_KEY',
    'django-insecure-campus-seguro-dev-key-cambiar-en-produccion'
)

# DEBUG: en producción debe ser False.
DEBUG = os.getenv('DJANGO_DEBUG', 'True').lower() in ('true', '1', 'yes')

# ALLOWED_HOSTS: en producción lista los dominios reales (ej: campus-seguro.duoc.cl)
ALLOWED_HOSTS = os.getenv('DJANGO_ALLOWED_HOSTS', '*').split(',')

# ── Aplicaciones instaladas ──────────────────────────────────
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'app',  # Aplicación principal de Campus Seguro
]

# ── Middleware ───────────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'campus_seguro.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
            # Context processor propio: agrega conteo de notificaciones
            # no leídas a todos los templates (usado en base.html sidebar).
            'app.context_processors.notificaciones_no_leidas',
        ],
    },
}]

WSGI_APPLICATION = 'campus_seguro.wsgi.application'

# ── Base de datos ────────────────────────────────────────────
# SQLite para desarrollo. En producción considerar PostgreSQL.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# ═══════════════════════════════════════════════════════════════
# SOPORTE PARA PROXY INVERSO / NGROK (desarrollo en equipo)
# ─────────────────────────────────────────────────────────────
# Cuando Django corre detrás de un proxy que termina SSL (ngrok,
# nginx, Heroku, etc.), necesita saber que las peticiones son HTTPS
# y confiar en los headers que envía el proxy.
#
# VARIABLES DE ENTORNO (agregar en .env de Jordan cuando use ngrok):
#   CSRF_TRUSTED_ORIGINS=https://abc123.ngrok-free.app
#   USE_X_FORWARDED_HOST=True
#   SECURE_PROXY_SSL_HEADER=True
#   AUTH0_LOGOUT_RETURN_URL=https://abc123.ngrok-free.app/login/
#
# Los compañeros NO necesitan configurar nada. Solo abrir la URL ngrok.
# Ver: docs/NGROK_EQUIPO.md para guía paso a paso.
# ═══════════════════════════════════════════════════════════════

# Lista de orígenes HTTPS confiables para validación CSRF.
# Requerido cuando los POST llegan desde un dominio HTTPS externo (ngrok).
# Django 4.0+ bloquea requests POST de orígenes no listados aquí.
# Formato: CSRF_TRUSTED_ORIGINS=https://abc123.ngrok-free.app,https://otro.app
_csrf_origins_raw = os.getenv('CSRF_TRUSTED_ORIGINS', '')
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_origins_raw.split(',') if o.strip()]

# Cuando Django está detrás de un proxy, confiar en el header X-Forwarded-Host
# para construir URLs absolutas correctas (usadas en logout y redirects).
USE_X_FORWARDED_HOST = os.getenv('USE_X_FORWARDED_HOST', 'False').lower() in ('true', '1', 'yes')

# Indica a Django que detecte HTTPS leyendo el header X-Forwarded-Proto.
# ngrok y nginx envían este header cuando la conexión externa es HTTPS.
if os.getenv('SECURE_PROXY_SSL_HEADER', 'False').lower() in ('true', '1', 'yes'):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ── Modelo de usuario personalizado ─────────────────────────
# Extiende AbstractUser con campos institucionales (rut, rol, sede, etc.)
# y el campo auth0_sub para vincular con Auth0.
AUTH_USER_MODEL = 'app.Usuario'

# ── URLs de autenticación ────────────────────────────────────
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/login/'

# ── Archivos estáticos ───────────────────────────────────────
STATIC_URL = '/static/'
# Los archivos CSS/JS del proyecto están en app/static/ (cargados automáticamente
# por Django via AppDirectoriesFinder). No se usa un directorio raíz adicional.
STATICFILES_DIRS = []
STATIC_ROOT = BASE_DIR / 'staticfiles'

# ── Archivos de medios (imágenes subidas por usuarios) ───────
# Fotos de evidencia de tickets, fotos de mantención, diagnósticos
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ── Localización ─────────────────────────────────────────────
LANGUAGE_CODE = 'es-cl'
TIME_ZONE = 'America/Santiago'
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Mensajes con tags compatibles con Bootstrap/CSS del proyecto ─
from django.contrib.messages import constants as messages_constants
MESSAGE_TAGS = {
    messages_constants.DEBUG: 'info',
    messages_constants.INFO: 'info',
    messages_constants.SUCCESS: 'success',
    messages_constants.WARNING: 'warning',
    messages_constants.ERROR: 'error',
}

# ═══════════════════════════════════════════════════════════════
# CONFIGURACIÓN AUTH0
# ─────────────────────────────────────────────────────────────
# Todas las variables se leen desde .env (nunca hardcodeadas).
# Si AUTH0_DOMAIN está vacío, el sistema usa autenticación Django
# local como fallback (útil para desarrollo sin credenciales Auth0).
#
# Documentación completa: docs/AUTH0_CONFIGURACION.md
# ═══════════════════════════════════════════════════════════════

# Dominio del tenant Auth0 (ej: campus-seguro.us.auth0.com)
AUTH0_DOMAIN = os.getenv('AUTH0_DOMAIN', '')

# Client ID de la aplicación Auth0 (Regular Web Application)
AUTH0_CLIENT_ID = os.getenv('AUTH0_CLIENT_ID', '')

# Client Secret de la aplicación Auth0
AUTH0_CLIENT_SECRET = os.getenv('AUTH0_CLIENT_SECRET', '')

# Audience del API Auth0 (ej: https://campus-seguro.us.auth0.com/api/v2/)
AUTH0_AUDIENCE = os.getenv('AUTH0_AUDIENCE', '')

# Namespace para custom claims en JWT (usado en Auth0 Action para roles)
# Ejemplo claim en token: {"https://campus-seguro.app/roles": ["gestor"]}
AUTH0_CLAIMS_NAMESPACE = os.getenv('AUTH0_CLAIMS_NAMESPACE', 'https://campus-seguro.app')

# Credenciales de la aplicación Machine-to-Machine para Management API.
# Usadas para crear/actualizar usuarios en Auth0 desde el backend.
AUTH0_MGMT_CLIENT_ID = os.getenv('AUTH0_MGMT_CLIENT_ID', '')
AUTH0_MGMT_CLIENT_SECRET = os.getenv('AUTH0_MGMT_CLIENT_SECRET', '')

# Nombre de la conexión (base de datos de usuarios) en Auth0
AUTH0_CONNECTION = os.getenv('AUTH0_CONNECTION', 'Username-Password-Authentication')

# URL fija de retorno después del logout de Auth0.
# Debe coincidir EXACTAMENTE con una de las entradas en
# Auth0 Dashboard → Application → Settings → Allowed Logout URLs.
# Al usar una URL fija (no request.build_absolute_uri) se evita el problema
# de que Django genere 127.0.0.1 cuando Auth0 espera localhost o viceversa.
AUTH0_LOGOUT_RETURN_URL = os.getenv('AUTH0_LOGOUT_RETURN_URL', 'http://localhost:8000/login/')

# Flag derivado: True si Auth0 está configurado y disponible para usar.
# Cuando es False, el sistema usa autenticación Django local (fallback).
AUTH0_ENABLED = bool(AUTH0_DOMAIN and AUTH0_CLIENT_ID and AUTH0_CLIENT_SECRET)

# Secret para validar requests entrantes del Auth0 Log Streaming webhook.
# Configurar en Auth0: Monitoring → Log Streams → Custom Webhook → Authorization.
# Si está vacío, el endpoint acepta cualquier request (solo para desarrollo).
AUTH0_WEBHOOK_SECRET = os.getenv('AUTH0_WEBHOOK_SECRET', '')
