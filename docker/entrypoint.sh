#!/bin/bash
# ============================================
# NexSCAT Entrypoint
# Automatiza configuración inicial del sistema
# ============================================

set -e  # Salir si hay errores

echo "Iniciando NexSCAT..."

# ============================================
# 1. Esperar a que PostgreSQL esté listo
# ============================================
echo " Esperando PostgreSQL..."
until nc -z db 5432; do
  echo "   PostgreSQL aún no está listo - esperando..."
  sleep 1
done
echo " PostgreSQL conectado"

# ============================================
# 2. Buscar y cargar configuración de entorno
# ============================================
echo "📥 Buscando configuración de entorno..."

if [ -f /app/.env.local ]; then
    echo " Usando .env.local existente"
    export $(grep -v '^#' /app/.env.local | tr -d '\r' | xargs)
elif [ -f /app/.env ]; then
    echo " Usando .env existente"
    export $(grep -v '^#' /app/.env | tr -d '\r' | xargs)
else
    echo " Generando .env automáticamente con valores por defecto..."
    cat > /app/.env << 'EOF'
DB_NAME=nexscat_db
DB_USER=postgres
DB_PASSWORD=1234
DB_HOST=db
DB_PORT=5432
DEBUG=True
SECRET_KEY=dev-secret-key-not-for-production
DJANGO_SETTINGS_MODULE=iscat.settings
export ALLOWED_HOSTS=${ALLOWED_HOSTS:-*}
SONARQUBE_URL=http://sonarqube:9000
SONARQUBE_TOKEN=
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0
ANALYSIS_MODE=parallel
USE_CELERY=True
MAX_PARALLEL_ANALYSIS=6
CELERY_WORKERS=6
ANALYSIS_TIMEOUT=1800
SONARQUBE_TIMEOUT=900
SOURCEMETER_TIMEOUT=900
SONAR_HEAP_MB=2048
SONAR_MIN_HEAP_MB=512
EOF
    echo " .env generado automáticamente"
    export $(grep -v '^#' /app/.env | tr -d '\r' | xargs)
fi

# ============================================
# 3. Generar SECRET_KEY si está vacío o es el default
# ============================================
CURRENT_SECRET_KEY="${SECRET_KEY:-}"

if [ -z "$CURRENT_SECRET_KEY" ] || [ "$CURRENT_SECRET_KEY" = "dev-secret-key-not-for-production" ]; then
    echo " Generando SECRET_KEY automáticamente..."
    NEW_SECRET_KEY=$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')

    if [ -f /app/.env.local ]; then
        sed -i "s|SECRET_KEY=.*|SECRET_KEY=$NEW_SECRET_KEY|" /app/.env.local
    elif [ -f /app/.env ]; then
        sed -i "s|SECRET_KEY=.*|SECRET_KEY=$NEW_SECRET_KEY|" /app/.env
    fi

    export SECRET_KEY=$NEW_SECRET_KEY
    echo " SECRET_KEY generado y configurado"
else
    echo " SECRET_KEY ya está configurado"
fi

# ============================================
# 4. Migraciones, seed y collectstatic
#    SOLO en el contenedor web
# ============================================
if [ "${CONTAINER_TYPE}" = "web" ]; then
    echo "🗄️  Aplicando migraciones de base de datos..."
    python manage.py migrate --noinput
    echo " Migraciones aplicadas"

    echo " Poblando datos iniciales (métricas de SourceMeter y SonarQube)..."
    python manage.py seed_data
    echo " Datos iniciales cargados"

    echo " Recolectando archivos estáticos..."
    python manage.py collectstatic --noinput --clear
    echo " Archivos estáticos recolectados"

    echo "⏳ Esperando que SonarQube esté operativo..."
    until curl -s -u admin:admin http://sonarqube:9000/api/system/status | grep -q '"status":"UP"'; do
    sleep 5
    done

echo "🔐 Asignando permiso Execute Analysis al admin..."
curl -s -u admin:admin -X POST \
    "http://sonarqube:9000/api/permissions/add_user" \
    -d "login=admin&permission=scan" || true
echo "✅ Permisos configurados"

    echo ""
    echo "======================================================================"
    echo " NexSCAT inicializado correctamente"
    echo "======================================================================"
    echo " Aplicación: http://localhost:8000"
    echo " SonarQube:  http://localhost:9000"
    echo " Flower:     http://localhost:5555"
    echo ""

    if [ -z "$SONARQUBE_TOKEN" ]; then
        echo "  SONARQUBE_TOKEN no configurado"
        echo "   Para habilitar análisis de código:"
        echo "   1. Acceder a http://localhost:9000"
        echo "   2. Login: admin/admin"
        echo "   3. My Account → Security → Generate Token"
        echo "   4. Agregar SONARQUBE_TOKEN a .env.local (o .env)"
        echo "   5. Reiniciar: docker compose -f docker-compose.local.yml restart web"
        echo ""
    fi
    echo "======================================================================"
    echo ""
else
    echo " Contenedor ${CONTAINER_TYPE} - saltando migraciones y seed"
fi

# ============================================
# 5. Ejecutar el comando según el tipo de contenedor
# ============================================
if [ "${CONTAINER_TYPE}" = "celery" ]; then
    echo "⚙️  Iniciando Celery Workers..."
    # Worker para tareas coordinadoras
    celery -A iscat worker --loglevel=info --concurrency=4 -Q celery &
    # Worker para subtareas de análisis
    celery -A iscat worker --loglevel=info --concurrency=4 -Q analysis

elif [ "${CONTAINER_TYPE}" = "flower" ]; then
    echo "🌸 Iniciando Flower..."
    exec celery -A iscat flower --port=5555

else
    echo "🌐 Iniciando Django..."
    if [ "${SCAT_MODE}" = "production" ]; then
        echo "   Modo producción → gunicorn"
        exec gunicorn iscat.wsgi:application \
            --bind 0.0.0.0:8000 \
            --workers ${GUNICORN_WORKERS:-4} \
            --timeout 300 \
            --access-logfile - \
            --error-logfile -
    else
        echo "   Modo desarrollo → runserver"
        exec python manage.py runserver 0.0.0.0:8000
    fi
fi
