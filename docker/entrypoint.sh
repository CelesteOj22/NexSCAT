#!/bin/bash
# ============================================
# NexSCAT Entrypoint
# Automatiza configuración inicial del sistema
# ============================================

set -e  # Salir si hay errores

echo "🚀 Iniciando NexSCAT..."

# ============================================
# 1. Esperar a que PostgreSQL esté listo
# ============================================
echo "⏳ Esperando PostgreSQL..."
until nc -z db 5432; do
  echo "   PostgreSQL aún no está listo - esperando..."
  sleep 1
done
echo "✅ PostgreSQL conectado"

# ============================================
# 2. Buscar y cargar configuración de entorno
# ============================================
echo "📥 Buscando configuración de entorno..."

if [ -f /app/.env.local ]; then
    echo "✅ Usando .env.local existente"
    export $(grep -v '^#' /app/.env.local | tr -d '\r' | xargs)
elif [ -f /app/.env ]; then
    echo "✅ Usando .env existente"
    export $(grep -v '^#' /app/.env | tr -d '\r' | xargs)
else
    echo "📝 Generando .env automáticamente con valores por defecto..."
    cat > /app/.env << 'EOF'
DB_NAME=nexscat_docker_dev
DB_USER=postgres
DB_PASSWORD=1234
DB_HOST=db
DB_PORT=5432
DEBUG=True
SECRET_KEY=dev-secret-key-not-for-production
DJANGO_SETTINGS_MODULE=iscat.settings
ALLOWED_HOSTS=localhost,127.0.0.1
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
    echo "✅ .env generado automáticamente"
    export $(grep -v '^#' /app/.env | tr -d '\r' | xargs)
fi

# ============================================
# 3. Generar SECRET_KEY si está vacío o es el default
# ============================================
CURRENT_SECRET_KEY="${SECRET_KEY:-}"

if [ -z "$CURRENT_SECRET_KEY" ] || [ "$CURRENT_SECRET_KEY" = "dev-secret-key-not-for-production" ]; then
    echo "🔐 Generando SECRET_KEY automáticamente..."
    NEW_SECRET_KEY=$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
    
    # Actualizar en el archivo de configuración actual
    if [ -f /app/.env.local ]; then
        sed -i "s|SECRET_KEY=.*|SECRET_KEY=$NEW_SECRET_KEY|" /app/.env.local
    elif [ -f /app/.env ]; then
        sed -i "s|SECRET_KEY=.*|SECRET_KEY=$NEW_SECRET_KEY|" /app/.env
    fi
    
    # Exportar para esta sesión
    export SECRET_KEY=$NEW_SECRET_KEY
    echo "✅ SECRET_KEY generado y configurado"
else
    echo "✅ SECRET_KEY ya está configurado"
fi

# ============================================
# 4. Ejecutar migraciones de base de datos
# ============================================
# 🔧 IMPORTANTE: Solo ejecutar si SKIP_MIGRATIONS != True
if [ "$SKIP_MIGRATIONS" != "True" ]; then
    echo "🗄️  Aplicando migraciones de base de datos..."
    python manage.py migrate --noinput
    echo "✅ Migraciones aplicadas"
    
    # ============================================
    # 4.5. Poblar datos iniciales (métricas + admin)
    # ============================================
    echo "🌱 Poblando datos iniciales (métricas de SourceMeter y SonarQube)..."
    python manage.py seed_data
    echo "✅ Datos iniciales cargados"
else
    echo "⏭️  Saltando migraciones (SKIP_MIGRATIONS=True)"
    echo "   Las migraciones y datos fueron ejecutados por el contenedor 'web'"
fi

# ============================================
# 5. Recolectar archivos estáticos (solo si no es Celery/Flower)
# ============================================
# Solo web hace collectstatic
if [ "$SKIP_MIGRATIONS" != "True" ]; then
    echo "📦 Recolectando archivos estáticos..."
    python manage.py collectstatic --noinput --clear
    echo "✅ Archivos estáticos recolectados"
fi

# ============================================
# 6. Mostrar información del sistema (solo en web)
# ============================================
if [ "$SKIP_MIGRATIONS" != "True" ]; then
    echo ""
    echo "======================================================================"
    echo "✅ NexSCAT inicializado correctamente"
    echo "======================================================================"
    echo "🌐 Aplicación: http://localhost:8000"
    echo "📊 SonarQube: http://localhost:9000"
    echo "🌺 Flower: http://localhost:5555"
    echo ""

    # Verificar token de SonarQube
    if [ -z "$SONARQUBE_TOKEN" ]; then
        echo "⚠️  SONARQUBE_TOKEN no configurado"
        echo "   Para habilitar análisis de código:"
        echo "   1. Acceder a http://localhost:9000"
        echo "   2. Login: admin/admin"
        echo "   3. My Account → Security → Generate Token"
        echo "   4. Agregar SONARQUBE_TOKEN a .env.local (o .env)"
        echo "   5. Reiniciar: docker-compose -f docker-compose_local.yml restart"
        echo ""
    fi

    echo "======================================================================"
    echo ""
fi

# ============================================
# 7. Ejecutar el comando pasado al contenedor
# ============================================
exec "$@"
