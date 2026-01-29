"""
Django settings for iscat project.

Configuración adaptativa según entorno:
- Desarrollo local (Windows/Linux)
- Docker local (alto rendimiento)
- AWS/Producción (recursos limitados)
"""

import os
import sys
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ============================================
# CONFIGURACIÓN DE ANÁLISIS ADAPTATIVA
# ============================================
try:
    from .config import AnalysisConfig
    ANALYSIS_CONFIG = AnalysisConfig

    # Loguear configuración al iniciar (solo en debug)
    if os.environ.get('DEBUG', 'False') == 'True':
        AnalysisConfig.log_config()
except ImportError:
    # Fallback si config.py no existe aún
    class AnalysisConfig:
        MODE = 'production'
        MAX_PARALLEL_ANALYSIS = 1
        ENABLE_PARALLEL = False
        USE_CELERY = False
        ANALYSIS_TIMEOUT = 600
        CELERY_WORKERS = 1
        CELERY_WORKER_PREFETCH_MULTIPLIER = 1
        CELERY_WORKER_MAX_TASKS_PER_CHILD = 50
        CELERY_TASK_ACKS_LATE = True
        SONARQUBE_TIMEOUT = 600
        SOURCEMETER_TIMEOUT = 300
        SONAR_HEAP_MB = 512
        SONAR_MIN_HEAP_MB = 128
    ANALYSIS_CONFIG = AnalysisConfig

# ============================================
# SEGURIDAD
# ============================================
SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'django-insecure-#eqw8y+(p-0%u1_(dzap5l@9jn6i$m0by+js7=d2f40)@$tw*2'
)

DEBUG = os.environ.get('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.environ.get(
    'ALLOWED_HOSTS',
    'localhost,127.0.0.1'
).split(',')

# ============================================
# DETECCIÓN DE ENTORNO
# ============================================
IS_DOCKER = os.path.exists('/.dockerenv') or os.environ.get('RUNNING_IN_DOCKER', False)
IS_WINDOWS = sys.platform.startswith('win')
IS_LINUX = sys.platform.startswith('linux')

# ============================================
# Application definition
# ============================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'main.apps.MainConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'iscat.urls'

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
            ],
        },
    },
]

WSGI_APPLICATION = 'iscat.wsgi.application'

# ============================================
# SESSION CONFIGURATION
# ============================================
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 86400  # 24 horas
SESSION_SAVE_EVERY_REQUEST = False

# ============================================
# DATABASE
# ============================================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'postgres'),
        'USER': os.environ.get('DB_USER', 'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD', '1234'),
        'HOST': os.environ.get('DB_HOST', 'localhost' if not IS_DOCKER else 'db'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'OPTIONS': {
            'connect_timeout': 10,
            'options': '-c statement_timeout=30000',
        },
        'CONN_MAX_AGE': 600,
        'ATOMIC_REQUESTS': True,
    }
}

# ============================================
# CELERY CONFIGURATION
# ============================================
if ANALYSIS_CONFIG.USE_CELERY:
    # Celery habilitado - Análisis paralelo
    CELERY_BROKER_URL = os.environ.get(
        'CELERY_BROKER_URL',
        'redis://localhost:6379/0' if not IS_DOCKER else 'redis://redis:6379/0'
    )
    CELERY_RESULT_BACKEND = os.environ.get(
        'CELERY_RESULT_BACKEND',
        'redis://localhost:6379/0' if not IS_DOCKER else 'redis://redis:6379/0'
    )

    # Serialización
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_TIMEZONE = 'America/Argentina/Buenos_Aires'

    # Tracking y timeouts
    CELERY_TASK_TRACK_STARTED = True
    CELERY_TASK_TIME_LIMIT = ANALYSIS_CONFIG.ANALYSIS_TIMEOUT

    # Workers
    CELERY_WORKER_CONCURRENCY = ANALYSIS_CONFIG.CELERY_WORKERS
    CELERY_WORKER_PREFETCH_MULTIPLIER = ANALYSIS_CONFIG.CELERY_WORKER_PREFETCH_MULTIPLIER
    CELERY_WORKER_MAX_TASKS_PER_CHILD = ANALYSIS_CONFIG.CELERY_WORKER_MAX_TASKS_PER_CHILD
    CELERY_TASK_ACKS_LATE = ANALYSIS_CONFIG.CELERY_TASK_ACKS_LATE

    # Pool configuration
    CELERY_WORKER_POOL = 'prefork'
    CELERY_WORKER_POOL_RESTARTS = True

    # Results
    CELERY_RESULT_EXPIRES = 3600
    CELERY_TASK_IGNORE_RESULT = False

    # Retry configuration
    CELERY_TASK_RETRY_MAX = 3
    CELERY_TASK_DEFAULT_RETRY_DELAY = 60

    # IMPORTANTE: Deshabilitar eager mode
    CELERY_TASK_ALWAYS_EAGER = False
    CELERY_TASK_EAGER_PROPAGATES = False

    # Logging
    CELERY_WORKER_HIJACK_ROOT_LOGGER = False
    CELERY_WORKER_LOG_FORMAT = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
    CELERY_WORKER_SEND_TASK_EVENTS = True
    CELERY_TASK_SEND_SENT_EVENT = True
else:
    # Celery deshabilitado - Análisis secuencial
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True

# ============================================
# PASSWORD VALIDATION
# ============================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ============================================
# INTERNATIONALIZATION
# ============================================
LANGUAGE_CODE = 'es-ar'
TIME_ZONE = 'America/Argentina/Buenos_Aires'
USE_I18N = True
USE_TZ = True

# ============================================
# STATIC FILES
# ============================================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# ============================================
# MEDIA FILES
# ============================================
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
os.makedirs(MEDIA_ROOT, exist_ok=True)
os.makedirs(STATIC_ROOT, exist_ok=True)

# ============================================
# DEFAULT PRIMARY KEY FIELD TYPE
# ============================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ============================================
# RUTAS DE HERRAMIENTAS
# ============================================
def get_tool_paths():
    if IS_DOCKER:
        return {
            'sonar_scanner': '/app/tools/linux/sonar-scanner/bin/sonar-scanner',
            'sourcemeter': '/app/tools/linux/sourcemeter/Java/SourceMeterJava',
        }
    elif IS_WINDOWS:
        return {
            'sonar_scanner': os.environ.get('SONAR_SCANNER_PATH', r'D:\sonar\sonar-scanner-4.7.0.2747-windows\bin\sonar-scanner.bat'),
            'sourcemeter': os.environ.get('SOURCEMETER_PATH', r'D:\sonar\SourceMeter-10.0.0-x64-Windows\Java\SourceMeterJava.exe'),
        }
    else:
        return {
            'sonar_scanner': os.environ.get('SONAR_SCANNER_PATH', '/usr/local/bin/sonar-scanner'),
            'sourcemeter': os.environ.get('SOURCEMETER_PATH', '/usr/local/bin/SourceMeterJava'),
        }

TOOL_PATHS = get_tool_paths()
SONAR_SCANNER_PATH = TOOL_PATHS['sonar_scanner']
SOURCEMETER_PATH = TOOL_PATHS['sourcemeter']

# ============================================
# SONARQUBE CONFIGURATION
# ============================================
SONARQUBE_URL = os.environ.get(
    'SONARQUBE_URL',
    'http://localhost:9000' if not IS_DOCKER else 'http://sonarqube:9000'
)
SONARQUBE_TOKEN = os.environ.get('SONARQUBE_TOKEN', '')

# Memoria para SonarQube
SONAR_HEAP_MB = getattr(ANALYSIS_CONFIG, 'SONAR_HEAP_MB', 512)
SONAR_MIN_HEAP_MB = getattr(ANALYSIS_CONFIG, 'SONAR_MIN_HEAP_MB', 128)
SONAR_CE_JAVAOPTS = f'-Xmx{SONAR_HEAP_MB}m -Xms{SONAR_MIN_HEAP_MB}m'
SONAR_WEB_JAVAOPTS = f'-Xmx{SONAR_HEAP_MB}m -Xms{SONAR_MIN_HEAP_MB}m'

if not DEBUG and not SONARQUBE_TOKEN:
    import warnings
    warnings.warn("⚠️  SONARQUBE_TOKEN no está configurado")

# ============================================
# TIMEOUTS
# ============================================
ANALYSIS_TIMEOUT = ANALYSIS_CONFIG.ANALYSIS_TIMEOUT
SONARQUBE_TIMEOUT = getattr(ANALYSIS_CONFIG, 'SONARQUBE_TIMEOUT', 900)
SOURCEMETER_TIMEOUT = getattr(ANALYSIS_CONFIG, 'SOURCEMETER_TIMEOUT', 600)

# ============================================
# LOGGING
# ============================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {'format': '{levelname} {asctime} {module} {message}', 'style': '{'},
        'simple': {'format': '{levelname} {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'verbose'},
        'file': {'class': 'logging.FileHandler', 'filename': BASE_DIR / 'logs' / 'django.log', 'formatter': 'verbose'},
    },
    'root': {'handlers': ['console'], 'level': 'INFO'},
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'main': {'handlers': ['console', 'file'] if not IS_DOCKER else ['console'], 'level': 'DEBUG' if DEBUG else 'INFO', 'propagate': False},
        'celery': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'celery.task': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}

os.makedirs(BASE_DIR / 'logs', exist_ok=True)

# ============================================
# SECURITY SETTINGS
# ============================================
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = 'DENY'

# ============================================
# CONFIGURACIÓN PERSONALIZADA
# ============================================
FILE_UPLOAD_MAX_MEMORY_SIZE = 104857600
DATA_UPLOAD_MAX_MEMORY_SIZE = 104857600

# ============================================
# VARIABLES PARA DOCKER COMPOSE
# ============================================
def get_docker_env_vars():
    return {
        'SCAT_MODE': ANALYSIS_CONFIG.MODE,
        'CELERY_WORKERS': str(ANALYSIS_CONFIG.CELERY_WORKERS),
        'SONAR_CE_JAVAOPTS': SONAR_CE_JAVAOPTS,
        'SONAR_WEB_JAVAOPTS': SONAR_WEB_JAVAOPTS,
        'MAX_PARALLEL_ANALYSIS': str(ANALYSIS_CONFIG.MAX_PARALLEL_ANALYSIS),
    }

if __name__ != '__main__':
    DOCKER_ENV_VARS = get_docker_env_vars()

# ============================================
# DEBUG TOOLBAR
# ============================================
if DEBUG and not IS_DOCKER:
    try:
        import debug_toolbar
        INSTALLED_APPS += ['debug_toolbar']
        MIDDLEWARE = ['debug_toolbar.middleware.DebugToolbarMiddleware'] + MIDDLEWARE
        INTERNAL_IPS = ['127.0.0.1']
    except ImportError:
        pass

# ============================================
# RESUMEN DE CONFIGURACIÓN
# ============================================
if DEBUG:
    import logging
    logger = logging.getLogger(__name__)
    logger.info("=" * 70)
    logger.info("🚀 NexSCAT - Configuración Cargada")
    logger.info("=" * 70)
    logger.info(f"📦 Entorno: {'🐳 Docker' if IS_DOCKER else '💻 Local'}")
    logger.info(f"🖥️  Sistema: {'Windows' if IS_WINDOWS else 'Linux' if IS_LINUX else 'Mac'}")
    logger.info(f"🐛 DEBUG: {DEBUG}")
    logger.info(f"🗄️  Base de datos: {DATABASES['default']['HOST']}:{DATABASES['default']['PORT']}")
    logger.info(f"🔍 SonarQube: {SONARQUBE_URL}")
    logger.info(f"⚙️  Modo análisis: {ANALYSIS_CONFIG.MODE.upper()}")
    logger.info(f"⚡ Análisis paralelos: {ANALYSIS_CONFIG.MAX_PARALLEL_ANALYSIS}")
    logger.info(f"🐰 Celery: {'✅ Habilitado' if ANALYSIS_CONFIG.USE_CELERY else '❌ Deshabilitado'}")

    if ANALYSIS_CONFIG.USE_CELERY:
        logger.info(f"👷 Workers Celery: {ANALYSIS_CONFIG.CELERY_WORKERS}")
        logger.info(f"🔧 Prefetch: {CELERY_WORKER_PREFETCH_MULTIPLIER}")
        logger.info(f"🔄 Max tasks/child: {CELERY_WORKER_MAX_TASKS_PER_CHILD}")

    logger.info(f"⏱️  Timeout total: {ANALYSIS_TIMEOUT}s ({ANALYSIS_TIMEOUT//60}min)")
    logger.info(f"🔵 Timeout SonarQube: {SONARQUBE_TIMEOUT}s ({SONARQUBE_TIMEOUT//60}min)")
    logger.info(f"🟢 Timeout SourceMeter: {SOURCEMETER_TIMEOUT}s ({SOURCEMETER_TIMEOUT//60}min)")
    logger.info(f"💾 SonarQube Heap: {SONAR_HEAP_MB}MB (min: {SONAR_MIN_HEAP_MB}MB)")
    logger.info("=" * 70)