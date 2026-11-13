"""Configuración del POS Sayariy Grill."""
import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# En producción define DJANGO_SECRET_KEY y DJANGO_DEBUG=0 (ver iniciar.bat)
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insegura-cambiar-en-produccion")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1" and not os.environ.get("VERCEL")
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",")
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o]

# Publicado en internet con HTTPS (Vercel / Azure)
if os.environ.get("DJANGO_HTTPS") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "pos",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "pos.middleware.DispositivoMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "pos.context_processors.negocio",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Local: SQLite. En la nube: variable DATABASE_URL (PostgreSQL en Azure)
# En Vercel cada función es efímera: una conexión por petición (conn_max_age=0)
EN_VERCEL = bool(os.environ.get("VERCEL"))
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=0 if EN_VERCEL else 60, conn_health_checks=not EN_VERCEL,
    )
}

AUTH_USER_MODEL = "pos.Usuario"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "inicio"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 6}},
]

LANGUAGE_CODE = "es"
TIME_ZONE = "America/La_Paz"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# WhiteNoise sirve los estilos directamente desde /static (sin collectstatic en Vercel)
WHITENOISE_USE_FINDERS = True

MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", BASE_DIR / "media"))

# Fotos de productos: en la nube van a Azure Blob Storage (Vercel no guarda archivos)
AZURE_CONEXION = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
if AZURE_CONEXION:
    STORAGES["default"] = {
        "BACKEND": "storages.backends.azure_storage.AzureStorage",
        "OPTIONS": {"connection_string": AZURE_CONEXION, "azure_container": "media",
                    "expiration_secs": None, "overwrite_files": False},
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# En internet: solo equipos autorizados por la administradora (en la red local no hace falta)
REQUIERE_DISPOSITIVO = os.environ.get("DJANGO_REQUIERE_DISPOSITIVO", "0") == "1"

# Caché en la base de datos: los bloqueos por intentos fallidos se comparten entre procesos
CACHES = {"default": {"BACKEND": "django.core.cache.backends.db.DatabaseCache", "LOCATION": "pos_cache"}}

# La sesión dura 12 horas (un turno largo)
SESSION_COOKIE_AGE = 60 * 60 * 12

LOGGING = {
    "version": 1,
    "handlers": {"consola": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["consola"], "level": "WARNING"},
}
