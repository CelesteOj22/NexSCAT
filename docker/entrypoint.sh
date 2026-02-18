#!/bin/bash
# ============================================
# NexSCAT Entrypoint
# Automatiza configuración inicial del sistema
# ============================================

set -e  # Salir si hay errores

echo " Iniciando NexSCAT..."

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
# 2. Crear .env.local si no existe
# ============================================
if [ ! -f /app/.env.local ]; then
    echo "📝 Creando archivo .env.local desde plantilla..."
    cp /app/.env.local.example /app/.env.local
    echo " Archivo .env.local creado"
else
    echo " Archivo .env.local ya existe"
fi

# ============================================
# 3. Generar SECRET_KEY si está vacío o es el default
# ============================================
CURRENT_SECRET_KEY=$(grep "^SECRET_KEY=" /app/.env.local | cut -d '=' -f2-)

if [ -z "$CURRENT_SECRET_KEY" ] || [ "$CURRENT_SECRET_KEY" = "dev-secret-key-not-for-production" ]; then
    echo " Generando SECRET_KEY automáticamente..."
    NEW_SECRET_KEY=$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
    
    # Reemplazar en .env.local
    sed -i "s|SECRET_KEY=.*|SECRET_KEY=$NEW_SECRET_KEY|" /app/.env.local
    
    # Exportar para esta sesión
    export SECRET_KEY=$NEW_SECRET_KEY
    echo " SECRET_KEY generado y configurado"
else
    echo " SECRET_KEY ya está configurado"
fi

# ============================================
# 4. Cargar variables de entorno desde .env.local
# ============================================
echo " Cargando variables de entorno..."
export $(grep -v '^#' /app/.env.local | tr -d '\r' | xargs)

# ============================================
# 5. Ejecutar migraciones de base de datos
# ============================================
# 🔧 IMPORTANTE: Solo ejecutar si SKIP_MIGRATIONS != True
if [ "$SKIP_MIGRATIONS" != "True" ]; then
    echo "  Aplicando migraciones de base de datos..."
    python manage.py migrate --noinput
    echo " Migraciones aplicadas"
    
    # ============================================
    # 5.5. Poblar datos iniciales (métricas + admin)
    # ============================================
    echo " Poblando datos iniciales (métricas de SourceMeter y SonarQube)..."
    python manage.py seed_data
    echo " Datos iniciales cargados"
else
    echo " Saltando migraciones (SKIP_MIGRATIONS=True)"
    echo "   Las migraciones y datos fueron ejecutados por el contenedor 'web'"
fi

# ============================================
# 6. Recolectar archivos estáticos (solo si no es Celery/Flower)
# ============================================
# Solo web hace collectstatic
if [ "$SKIP_MIGRATIONS" != "True" ]; then
    echo " Recolectando archivos estáticos..."
    python manage.py collectstatic --noinput --clear
    echo " Archivos estáticos recolectados"
fi

# ============================================
# 7. Mostrar información del sistema (solo en web)
# ============================================
if [ "$SKIP_MIGRATIONS" != "True" ]; then
    echo ""
    echo "======================================================================"
    echo " NexSCAT inicializado correctamente"
    echo "======================================================================"
    echo " Aplicación: http://localhost:8000"
    echo " SonarQube: http://localhost:9000"
    echo " Flower: http://localhost:5555"
    echo ""

    # Verificar token de SonarQube
    if [ -z "$SONARQUBE_TOKEN" ]; then
        echo "⚠️  SONARQUBE_TOKEN no configurado"
        echo "   Para habilitar análisis de código:"
        echo "   1. Acceder a http://localhost:9000"
        echo "   2. Login: admin/admin"
        echo "   3. My Account → Security → Generate Token"
        echo "   4. Agregar SONARQUBE_TOKEN a .env.local"
        echo "   5. Reiniciar: docker-compose -f docker-compose_local.yml restart"
        echo ""
    fi

    echo "======================================================================"
    echo ""
fi

# ============================================
# 8. Ejecutar el comando pasado al contenedor
# ============================================
exec "$@"