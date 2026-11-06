import os
from .base import *

DEBUG = True
SECRET_KEY = 'test-key-for-running-tests-only'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'test_db.sqlite3',
    }
}


# Hashing más rápido para agilizar las pruebas
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Excluir SessionRefresh de OIDC en el runner de pruebas para permitir client.force_login
MIDDLEWARE = [
    m for m in MIDDLEWARE
    if m != 'mozilla_django_oidc.middleware.SessionRefresh'
]

# Configuración OIDC mock para pruebas
KEYCLOAK_SERVER_URL = "http://localhost:8080"
KEYCLOAK_REALM = "GlobalExchangeRealm"
KEYCLOAK_CLIENT_ID = "django-app"
KEYCLOAK_CLIENT_SECRET = "test-secret"

OIDC_OP_AUTHORIZATION_ENDPOINT = (
    f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth"
)
OIDC_OP_TOKEN_ENDPOINT = (
    f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
)
OIDC_OP_USER_ENDPOINT = (
    f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/userinfo"
)
OIDC_OP_JWKS_ENDPOINT = (
    f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
)
OIDC_OP_LOGOUT_ENDPOINT = (
    f"{KEYCLOAK_SERVER_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/logout"
)

OIDC_RP_CLIENT_ID = KEYCLOAK_CLIENT_ID
OIDC_RP_CLIENT_SECRET = KEYCLOAK_CLIENT_SECRET
OIDC_RP_SIGN_ALGO = "RS256"
OIDC_RP_SCOPES = "openid email profile"
OIDC_CREATE_USER = True
OIDC_VERIFY_SSL = False

# Facturación Electrónica Mock para suite de pruebas (0 consumo de cuota real)
FACTURA_SEGURA_LIVE_ENABLED = False

# SCRUM-125: la suite completa se ejecuta offline; cualquier intento de API falla.
TEST_RUNNER = 'config.test_runner.OfflineDiscoverRunner'

