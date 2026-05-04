#!/bin/bash
# ============================================
# setup-hetzner.sh
# Setup completo de NexSCAT en Hetzner CX42
# Ejecutar como root o con sudo
# ============================================

set -e

REPO_URL="https://github.com/TU_USUARIO/NexSCAT.git"   # ← CAMBIAR
APP_DIR="/opt/nexscat"

echo "=============================================="
echo " NexSCAT — Setup Hetzner CX42"
echo "=============================================="

# ── 1. Sistema base ────────────────────────────
echo ""
echo "[1/6] Actualizando sistema..."
apt-get update && apt-get upgrade -y

# ── 2. Docker ──────────────────────────────────
echo ""
echo "[2/6] Instalando Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
else
    echo "   Docker ya instalado ($(docker --version))"
fi

# ── 3. Git LFS — CRÍTICO para SourceMeter ─────
echo ""
echo "[3/6] Instalando Git y Git LFS..."
apt-get install -y git git-lfs
git lfs install --system
echo "   Git LFS instalado"

# ── 4. Configurar vm.max_map_count para SonarQube ──
echo ""
echo "[4/6] Configurando kernel para SonarQube..."
sysctl -w vm.max_map_count=262144
echo "vm.max_map_count=262144" >> /etc/sysctl.conf
echo "   vm.max_map_count=262144 configurado"

# ── 5. Clonar repositorio ──────────────────────
echo ""
echo "[5/6] Clonando repositorio..."
if [ -d "$APP_DIR" ]; then
    echo "   Directorio ya existe — actualizando..."
    cd "$APP_DIR"
    git pull
    git lfs pull       # ← Descarga el binario real de SourceMeter
else
    git clone "$REPO_URL" "$APP_DIR"
    cd "$APP_DIR"
    git lfs pull       # ← Descarga el binario real de SourceMeter
fi

# Verificar que el binario de SourceMeter no sea un puntero LFS
SM_FILE=$(find "$APP_DIR/tools" -name "SourceMeter*.tgz" 2>/dev/null | head -n 1)
if [ -n "$SM_FILE" ]; then
    SIZE=$(stat -c%s "$SM_FILE")
    if [ "$SIZE" -lt 10000 ]; then
        echo ""
        echo "⚠️  ADVERTENCIA: El archivo SourceMeter parece ser un puntero LFS ($SIZE bytes)."
        echo "   Verificá que Git LFS esté configurado en el repositorio."
        echo "   Ejecutá: cd $APP_DIR && git lfs pull"
        echo ""
    else
        echo "   SourceMeter OK ($SIZE bytes)"
    fi
else
    echo "   ⚠️  No se encontró el archivo SourceMeter en tools/"
fi

# ── 6. Configurar .env ────────────────────────
echo ""
echo "[6/6] Configuración de entorno..."
if [ ! -f "$APP_DIR/.env" ]; then
    if [ -f "$APP_DIR/.env.cloud" ]; then
        cp "$APP_DIR/.env.cloud" "$APP_DIR/.env"
        echo "   .env creado desde .env.cloud"
        echo ""
        echo "  ╔══════════════════════════════════════════╗"
        echo "  ║  EDITÁ .env ANTES DE CONTINUAR          ║"
        echo "  ║  nano $APP_DIR/.env                     ║"
        echo "  ║  Completá: DB_PASSWORD, SECRET_KEY,     ║"
        echo "  ║            ALLOWED_HOSTS (IP del server)║"
        echo "  ╚══════════════════════════════════════════╝"
        echo ""
    else
        echo "   ⚠️  No se encontró .env.cloud — creá el .env manualmente"
    fi
else
    echo "   .env ya existe"
fi

echo ""
echo "=============================================="
echo " Setup completado."
echo ""
echo " Próximos pasos:"
echo "   1. nano $APP_DIR/.env          # Completar variables"
echo "   2. cd $APP_DIR"
echo "   3. docker compose -f docker-compose.cloud.yml build"
echo "   4. docker compose -f docker-compose.cloud.yml up -d"
echo "   5. docker compose -f docker-compose.cloud.yml logs -f"
echo ""
echo " URL de la aplicación: http://$(curl -s ifconfig.me)"
echo "=============================================="
