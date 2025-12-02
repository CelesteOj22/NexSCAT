## docker/Dockerfile
# ============================================
# Dockerfile para SCAT - Multi-entorno
# ============================================
FROM python:3.11-slim

# Evitar prompts interactivos durante la instalación
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Etiquetas de metadata
LABEL maintainer="ceojedarodriguez@gmail.com"
LABEL description="NexSCAT - Sistema de analisis estatico de codigo"

# ============================================
# Instalar dependencias del sistema
# ============================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    unzip \
    curl \
    git \
    ca-certificates \
    gnupg \
    postgresql-client \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# ============================================
# Instalar Java 17 (adoptium/temurin)
# ============================================
RUN mkdir -p /etc/apt/keyrings && \
    wget -O - https://packages.adoptium.net/artifactory/api/gpg/key/public | tee /etc/apt/keyrings/adoptium.asc && \
    echo "deb [signed-by=/etc/apt/keyrings/adoptium.asc] https://packages.adoptium.net/artifactory/deb $(awk -F= '/^VERSION_CODENAME/{print$2}' /etc/os-release) main" | tee /etc/apt/sources.list.d/adoptium.list && \
    apt-get update && \
    apt-get install -y temurin-17-jdk && \
    rm -rf /var/lib/apt/lists/*

# Verificar instalación de Java
RUN java -version

# ============================================
# Configurar directorio de trabajo
# ============================================
WORKDIR /app

# ============================================
# Instalar dependencias de Python
# ============================================
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# ============================================
# Crear estructura de directorios
# ============================================
RUN mkdir -p /app/tools/linux \
    && mkdir -p /app/media \
    && mkdir -p /app/staticfiles

# ============================================
# DESCARGAR E INSTALAR SONAR SCANNER (LINUX)
# ============================================
RUN echo "Descargando SonarScanner..." && \
    wget -q https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-5.0.1.3006-linux.zip && \
    unzip -q sonar-scanner-cli-5.0.1.3006-linux.zip -d /app/tools/linux/ && \
    mv /app/tools/linux/sonar-scanner-5.0.1.3006-linux /app/tools/linux/sonar-scanner && \
    rm sonar-scanner-cli-5.0.1.3006-linux.zip && \
    chmod +x /app/tools/linux/sonar-scanner/bin/sonar-scanner && \
    echo "SonarScanner instalado correctamente"

# ============================================
# INSTALAR SOURCEMETER (desde archivo local)
# ============================================
# Copiar el archivo .tgz desde la carpeta tools/
COPY tools/SourceMeter-10.2.0-x64-Linux.tgz /tmp/sourcemeter.tgz

# Descomprimir e instalar (con inspección de estructura)
RUN echo "Instalando SourceMeter desde archivo local..." && \
    tar -xzf /tmp/sourcemeter.tgz -C /app/tools/linux/ && \
    rm /tmp/sourcemeter.tgz && \
    echo "Listando contenido de /app/tools/linux/:" && \
    ls -la /app/tools/linux/ && \
    SM_DIR=$(find /app/tools/linux -maxdepth 1 -type d -name "SourceMeter*" | head -n 1) && \
    echo "Directorio encontrado: $SM_DIR" && \
    mv "$SM_DIR" /app/tools/linux/sourcemeter && \
    echo "Listando contenido de sourcemeter:" && \
    ls -la /app/tools/linux/sourcemeter/ && \
    find /app/tools/linux/sourcemeter -type f -name "*Java*" -o -name "*Python*" -o -name "*CPP*" | head -20 && \
    chmod +x /app/tools/linux/sourcemeter/Java/SourceMeterJava 2>/dev/null || echo "SourceMeterJava no encontrado en Java/" && \
    chmod +x /app/tools/linux/sourcemeter/Python/SourceMeterPython 2>/dev/null || echo "SourceMeterPython no encontrado en Python/" && \
    chmod +x /app/tools/linux/sourcemeter/CPP/SourceMeterCPP 2>/dev/null || echo "SourceMeterCPP no encontrado en CPP/" && \
    chmod -R +x /app/tools/linux/sourcemeter/ 2>/dev/null || true && \
    echo "SourceMeter instalado correctamente"

# ============================================
# Configurar PATH para las herramientas
# ============================================
ENV PATH="/app/tools/linux/sonar-scanner/bin:/app/tools/linux/sourcemeter/Java:${PATH}"

# Verificar que las herramientas estén disponibles
RUN echo "Verificando herramientas instaladas..." && \
    sonar-scanner --version && \
    echo "PATH actual: $PATH"

# ============================================
# Copiar código de la aplicación
# ============================================
COPY . /app/

# ============================================
# Recolectar archivos estáticos
# ============================================
RUN python manage.py collectstatic --noinput || echo "No se pudo ejecutar collectstatic, continuando..."

# ============================================
# Configurar permisos
# ============================================
RUN chmod +x /app/docker/entrypoint.sh || echo "No se encontró entrypoint.sh"

# ============================================
# Exponer puerto
# ============================================
EXPOSE 8000

# ============================================
# Healthcheck
# ============================================
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# ============================================
# Comando por defecto
# ============================================
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]