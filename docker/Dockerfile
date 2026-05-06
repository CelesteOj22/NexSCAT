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
    bash \
    && rm -rf /var/lib/apt/lists/*

# ============================================
# Instalar Java 17 y Java 11 (adoptium/temurin)
# ============================================
RUN mkdir -p /etc/apt/keyrings && \
    wget -O - https://packages.adoptium.net/artifactory/api/gpg/key/public | tee /etc/apt/keyrings/adoptium.asc && \
    echo "deb [signed-by=/etc/apt/keyrings/adoptium.asc] https://packages.adoptium.net/artifactory/deb $(awk -F= '/^VERSION_CODENAME/{print$2}' /etc/os-release) main" | tee /etc/apt/sources.list.d/adoptium.list && \
    apt-get update && \
    apt-get install -y temurin-17-jdk temurin-11-jdk && \
    rm -rf /var/lib/apt/lists/*

# Java 17 como default del sistema
ENV JAVA_HOME=/usr/lib/jvm/temurin-17-jdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"

# Java 11 disponible para SourceMeter
ENV JAVA11_HOME=/usr/lib/jvm/temurin-11-jdk-amd64

# Verificar instalación
RUN java -version && \
    ${JAVA11_HOME}/bin/java -version
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
RUN mkdir -p /opt/tools \
    && mkdir -p /app/media \
    && mkdir -p /app/staticfiles

# ============================================
# DESCARGAR E INSTALAR SONAR SCANNER (LINUX)
# ============================================
RUN echo "Descargando SonarScanner..." && \
    wget -q https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-5.0.1.3006-linux.zip && \
    unzip -q sonar-scanner-cli-5.0.1.3006-linux.zip -d /opt/tools/ && \
    mv /opt/tools/sonar-scanner-5.0.1.3006-linux /opt/tools/sonar-scanner && \
    rm sonar-scanner-cli-5.0.1.3006-linux.zip && \
    chmod +x /opt/tools/sonar-scanner/bin/sonar-scanner && \
    echo "SonarScanner instalado correctamente"

# ============================================
# INSTALAR SOURCEMETER (desde archivo local)
# ============================================
COPY tools/SourceMeter-10.2.0-x64-Linux.tgz /tmp/sourcemeter.tgz

RUN echo "Instalando SourceMeter desde archivo local..." && \
    tar -xzf /tmp/sourcemeter.tgz -C /opt/tools/ && \
    rm /tmp/sourcemeter.tgz && \
    echo "Listando contenido de /opt/tools/:" && \
    ls -la /opt/tools/ && \
    SM_DIR=$(find /opt/tools -maxdepth 1 -type d -name "SourceMeter*" | head -n 1) && \
    echo "Directorio encontrado: $SM_DIR" && \
    mv "$SM_DIR" /opt/tools/sourcemeter && \
    echo "Listando contenido de sourcemeter:" && \
    ls -la /opt/tools/sourcemeter/ && \
    find /opt/tools/sourcemeter -type f -name "*Java*" -o -name "*Python*" -o -name "*CPP*" | head -20 && \
    chmod +x /opt/tools/sourcemeter/Java/SourceMeterJava 2>/dev/null || echo "SourceMeterJava no encontrado en Java/" && \
    chmod +x /opt/tools/sourcemeter/Python/SourceMeterPython 2>/dev/null || echo "SourceMeterPython no encontrado en Python/" && \
    chmod +x /opt/tools/sourcemeter/CPP/SourceMeterCPP 2>/dev/null || echo "SourceMeterCPP no encontrado en CPP/" && \
    chmod -R +x /opt/tools/sourcemeter/ 2>/dev/null || true && \
    echo "SourceMeter instalado correctamente"

# ============================================
# Configurar PATH para las herramientas
# ============================================
ENV PATH="/opt/tools/sonar-scanner/bin:/opt/tools/sourcemeter/Java:${PATH}"

# Verificar que las herramientas estén disponibles
RUN echo "Verificando herramientas instaladas..." && \
    sonar-scanner --version && \
    echo "PATH actual: $PATH"

# ============================================
# Copiar código de la aplicación
# ============================================
COPY . /app/
RUN sed -i 's/\r$//' /app/docker/entrypoint.sh && \
    chmod +x /app/docker/entrypoint.sh

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
# Entrypoint y comando por defecto
# ============================================
RUN find /app -name "*.pyc" -delete && find /app -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

ENTRYPOINT ["/app/docker/entrypoint.sh"]

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]