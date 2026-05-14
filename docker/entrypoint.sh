#!/bin/bash
# ============================================
# NexSCAT Entrypoint
# Automatiza configuración inicial del sistema
# ============================================

set -e

echo "Iniciando NexSCAT..."

# ============================================
# 1. Esperar a que PostgreSQL esté listo
# ============================================
echo "Esperando PostgreSQL..."
until nc -z db 5432; do
  echo "   PostgreSQL aún no está listo - esperando..."
  sleep 1
done
echo "PostgreSQL conectado"

# ============================================
# 2. Verificar configuración de entorno
# (Docker Compose ya inyecta las variables del .env)
# ============================================
echo "📥 Verificando configuración de entorno..."

if [ -z "$SECRET_KEY" ] || [ "$SECRET_KEY" = "dev-secret-key-not-for-production" ]; then
    echo "⚠️  SECRET_KEY no configurado, generando uno nuevo..."
    NEW_SECRET_KEY=$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
    export SECRET_KEY=$NEW_SECRET_KEY
    echo "✅ SECRET_KEY generado"
else
    echo "✅ SECRET_KEY configurado"
fi

# ============================================
# 3. Migraciones, seed y collectstatic
#    SOLO en el contenedor web
# ============================================
if [ "${CONTAINER_TYPE}" = "web" ]; then
    echo "🗄️  Aplicando migraciones de base de datos..."
    python manage.py migrate --noinput
    echo "✅ Migraciones aplicadas"

    echo "Poblando datos iniciales..."
    python manage.py seed_data
    echo "✅ Datos iniciales cargados"

    echo "Recolectando archivos estáticos..."
    python manage.py collectstatic --noinput --clear
    echo "✅ Archivos estáticos recolectados"

    echo "⏳ Esperando que SonarQube esté operativo..."
    until curl -s -u admin:admin http://sonarqube:9000/api/system/status | grep -q '"status":"UP"'; do
        sleep 5
    done

    echo "🔐 Asignando permisos en SonarQube..."
    curl -s -u admin:admin -X POST \
        "http://sonarqube:9000/api/permissions/add_user" \
        -d "login=admin&permission=scan" || true
    echo "✅ Permisos configurados"

    echo ""
    echo "======================================================================"
    echo "✅ NexSCAT inicializado correctamente"
    echo "======================================================================"
else
    echo "Contenedor ${CONTAINER_TYPE} - saltando migraciones y seed"
fi

# ============================================
# 4. Ejecutar el comando según el tipo de contenedor
# ============================================
if [ "${CONTAINER_TYPE}" = "celery" ]; then
    echo "⚙️  Iniciando Celery Workers..."
    celery -A iscat worker --loglevel=info --concurrency=4 -Q celery &
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
            --timeout 600 \
            --keep-alive 5 \
            --limit-request-line 0 \
            --limit-request-field_size 0 \
            --access-logfile - \
            --error-logfile -
    else
        echo "   Modo desarrollo → runserver"
        exec python manage.py runserver 0.0.0.0:8000
    fi
fi