import os
from pathlib import Path
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

# Carga variables de entorno
load_dotenv()

# Ruta base del proyecto (apunta a la raíz del repositorio)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Clave secreta y modo debug
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-default-key-change-in-production')
DEBUG = os.getenv('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '*').split(',')

ROOT_URLCONF = 'config.urls'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Aplicaciones de terceros
    'mozilla_django_oidc',
    # Aplicaciones propias
    'authentication',
    'customers',
    'payments',
    'rates',
    'transactions',
    'apps.cash',
    'apps.invoicing',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'customers.middleware.ActiveCustomerMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'mozilla_django_oidc.middleware.SessionRefresh',
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'authentication.context_processors.auth_roles',
                'customers.context_processors.active_customer',
                'rates.context_processors.unread_notifications',
            ],

        },
    },
]

# Configuración regional e internacionalización
LANGUAGE_CODE = 'es-es'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Archivos estáticos y multimedia
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Tipo de clave primaria por defecto
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Backends de autenticación (OIDC + Django local para admin)
AUTHENTICATION_BACKENDS = [
    'authentication.backends.KeycloakOIDCAuthenticationBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# URLs de redirección para autenticación
LOGIN_URL = '/oidc/authenticate/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# Configuración de Pasarela de Pagos Stripe (SCRUM-92)
STRIPE_PUBLIC_KEY = os.getenv('STRIPE_PUBLIC_KEY', 'pk_test_sample')
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', 'sk_test_sample')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', 'whsec_sample')
STRIPE_CURRENCY = os.getenv('STRIPE_CURRENCY', 'usd')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '{asctime} {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'rates': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# ==============================================================================
# FACTURACIÓN ELECTRÓNICA SIFEN / FACTURA SEGURA (SCRUM-110 / SCRUM-117)
# ==============================================================================
FACTURA_SEGURA_LIVE_ENABLED = os.getenv('FACTURA_SEGURA_LIVE_ENABLED', 'False').lower() in ('true', '1')
FACTURA_SEGURA_API_URL = os.getenv('FACTURA_SEGURA_API_URL', 'https://apitest.facturasegura.com.py')
FACTURA_SEGURA_EMAIL = os.getenv('FACTURA_SEGURA_EMAIL', '')
FACTURA_SEGURA_PASSWORD = os.getenv('FACTURA_SEGURA_PASSWORD', '')
FACTURA_SEGURA_TOKEN = os.getenv('FACTURA_SEGURA_TOKEN', '')
FACTURA_SEGURA_EMISOR_RUC = os.getenv('FACTURA_SEGURA_EMISOR_RUC', '80012345')
FACTURA_SEGURA_EMISOR_DV = os.getenv('FACTURA_SEGURA_EMISOR_DV', '7')
FACTURA_SEGURA_EMISOR_TIMBRADO = os.getenv('FACTURA_SEGURA_EMISOR_TIMBRADO', '12548963')
