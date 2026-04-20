# NexSCAT - Nexus Source Code Analysis Tool

> **Plataforma de análisis estático batch de proyectos Java**  
> Integra SonarQube + SourceMeter sobre Django + Celery + PostgreSQL + Redis  
> Arquitectura local-first para privacidad de código

---

## 📋 Requisitos del Sistema

- **Ubuntu 24.04 / 25.04** (nativo o VirtualBox)
- **Docker Engine** (no Docker Desktop)
- **Git**
- Mínimo **8 GB de RAM** recomendado
- Mínimo **20 GB de espacio en disco**

> ⚠️ **Análisis con SourceMeter en Windows/WSL2.**  
> SourceMeter requiere que sus binarios y el directorio de resultados estén en el mismo filesystem.  
> En Windows/WSL2 esto es imposible por la separación entre el overlay de Docker y los bind mounts del host.  
> Se debe ejecutar desde Linux o una VM Linux.

---

## 🚀 Instalación

### 1. Instalar Docker en Ubuntu

```bash
# Agregar repositorio oficial de Docker
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Ubuntu 25.04: usar repositorio 'noble' (24.04) por compatibilidad
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu noble stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Agregar usuario al grupo docker (evita usar sudo)
sudo usermod -aG docker $USER
newgrp docker
```

### 2. Clonar el repositorio

```bash
git clone https://github.com/CelesteOj22/nexscat.git
cd nexscat
```

### 3. Configurar variables de entorno

```bash
cp .env.example .env
```

Editá `.env` con tus valores. Mínimo requerido:

```env
DB_PASSWORD=tu_password
SECRET_KEY=tu_secret_key
SONARQUBE_TOKEN=     # se completa más adelante
SCAT_MODE=development
```

Para generar el `SECRET_KEY`:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

### 4. Crear carpetas necesarias

```bash
mkdir -p ~/nexscat/sm_results
mkdir -p ~/nexscat/proyectos
mkdir -p ~/nexscat/tools
```

### 5. Primer arranque (sin SourceMeter configurado)

```bash
docker compose -f docker-compose.local.yml up -d
```

Esperá a que todos los servicios estén healthy (puede tardar 2-3 minutos la primera vez):

```bash
docker compose -f docker-compose.local.yml ps
```

### 6. Configurar SonarQube

1. Accedé a [http://localhost:9000](http://localhost:9000)
2. Login: `admin` / `admin` → cambiá la contraseña cuando lo pida
3. Ir a: **My Account → Security → Generate Token**
4. Copiá el token y agregalo al `.env`:
   ```env
   SONARQUBE_TOKEN=squ_xxxxxxxxxxxxxxxxxxxxxxxx
   ```
5. Reiniciá los contenedores:
   ```bash
   docker compose -f docker-compose.local.yml restart
   ```

### 7. Copiar SourceMeter al host ⚠️ PASO OBLIGATORIO

Este paso es **crítico** para que el análisis con SourceMeter funcione correctamente.  
SourceMeter necesita que sus binarios y el directorio de resultados estén en el **mismo filesystem**.  
Al copiarlo al host, tanto `/opt/tools/sourcemeter` como `/opt/sm_results` quedan en el mismo filesystem de Ubuntu, evitando el error `Invalid cross-device link`.

```bash
# Asegurarse de que el contenedor esté corriendo
docker compose -f docker-compose.local.yml up -d celery_worker

# Copiar SourceMeter del contenedor al host
docker cp nexscat_celery_local:/opt/tools/sourcemeter ~/nexscat/tools/sourcemeter

# Reiniciar para que tome el bind mount
docker compose -f docker-compose.local.yml restart celery_worker web
```

### 8. Acceder a NexSCAT

- **Aplicación:** [http://localhost:8000](http://localhost:8000)
- **SonarQube:** [http://localhost:9000](http://localhost:9000)
- **Flower (monitor Celery):** [http://localhost:5555](http://localhost:5555)

---

## 📁 Agregar proyectos para analizar

Los proyectos Java deben copiarse a la carpeta `proyectos/` del repositorio:

```bash
# Copiar un proyecto manualmente
cp -r /ruta/al/proyecto ~/nexscat/proyectos/nombre-proyecto-1.0

# Si tenés los proyectos en una carpeta compartida de VirtualBox (sf_)
rsync -av --progress /media/sf_nombre_carpeta/ ~/nexscat/proyectos/
```

> `rsync` es recomendable para copias grandes: si se interrumpe, al correrlo de nuevo retoma donde quedó sin recopiar archivos ya transferidos.

La estructura debe quedar:

```
~/nexscat/proyectos/
├── proyecto-a-1.0/
│   ├── src/
│   ├── build.xml / pom.xml
│   └── ...
├── proyecto-b-2.3/
└── ...
```

Luego desde la interfaz web importás el proyecto con la ruta `/app/proyectos/nombre-proyecto-1.0`.

---

## ⚙️ Configuración

### Variables de entorno importantes

| Variable | Descripción | Valor por defecto |
|----------|-------------|-------------------|
| `DB_PASSWORD` | Contraseña de PostgreSQL | `1234` |
| `SECRET_KEY` | Clave secreta de Django | (requerido) |
| `SONARQUBE_TOKEN` | Token de autenticación SonarQube | (requerido) |
| `DEBUG` | Modo debug de Django | `True` |
| `SCAT_MODE` | Modo de análisis | `development` |
| `MAX_PARALLEL_ANALYSIS` | Análisis simultáneos | `2` |

### Modos de análisis (`SCAT_MODE`)

| Modo | Descripción | Timeout |
|------|-------------|---------|
| `development` | Local con recursos moderados | 7200s (2h) |
| `production` | Cloud / recursos limitados | 7200s (2h) |
| `balanced` | Balance rendimiento/recursos | 7200s (2h) |
| `performance` | Máximo rendimiento local | 1800s (30min) |
| `auto` | Detección automática ⚠️ puede poner 1200s | variable |

> ⚠️ Evitá el modo `auto` si tus proyectos tardan más de 20 minutos en analizarse.

---

## 🐳 Comandos Docker útiles

```bash
# Ver estado de los contenedores
docker compose -f docker-compose.local.yml ps

# Ver logs de un servicio
docker compose -f docker-compose.local.yml logs web --tail=100
docker compose -f docker-compose.local.yml logs celery_worker --tail=100

# Seguir logs en tiempo real
docker compose -f docker-compose.local.yml logs -f celery_worker

# Reiniciar un servicio específico
docker compose -f docker-compose.local.yml restart celery_worker

# Bajar todos los servicios
docker compose -f docker-compose.local.yml down

# Levantar todos los servicios
docker compose -f docker-compose.local.yml up -d

# Reconstruir imágenes (tras cambios en Dockerfile)
docker compose -f docker-compose.local.yml up -d --build
```

---

## 🗑️ Reiniciar análisis desde cero

Para borrar todos los datos de análisis y empezar de nuevo:

```bash
# 1. Borrar resultados de SourceMeter
rm -rf ~/nexscat/sm_results/*

# 2. Borrar datos de la base de datos
docker exec -it nexscat_web_local python manage.py shell -c "
from main.models import Project, Component, Class, ProjectMeasure, ComponentMeasure, ClassMeasure
ClassMeasure.objects.all().delete()
ComponentMeasure.objects.all().delete()
ProjectMeasure.objects.all().delete()
Class.objects.all().delete()
Component.objects.all().delete()
Project.objects.all().delete()
print('✅ Todo borrado')
"

# 3. Borrar proyectos de SonarQube
docker exec -it nexscat_web_local python manage.py shell -c "
import requests
from django.conf import settings
token = settings.SONARQUBE_TOKEN
url = settings.SONARQUBE_URL
projects = requests.get(f'{url}/api/projects/search', auth=(token, '')).json()
for p in projects.get('components', []):
    requests.post(f'{url}/api/projects/delete', auth=(token, ''), params={'project': p['key']})
    print(f'Borrado: {p[\"key\"]}')
"
```

---

## 🔍 Diagnóstico de errores

### Ver errores del análisis

```bash
# Errores generales
docker compose -f docker-compose.local.yml logs celery_worker --tail=200 | \
  grep -E "✅|❌|⚠️|critical error|succeeded|failed"

# Error específico de SourceMeter
docker compose -f docker-compose.local.yml logs celery_worker --tail=200 | \
  grep -A 10 "DirectoryBasedAnalysisTask"

# Timeout de tareas
docker compose -f docker-compose.local.yml logs celery_worker --tail=100 | \
  grep -E "TimeLimitExceeded|time limit|TIMEOUT"

# Ver CSVs generados por SourceMeter
find ~/nexscat/sm_results -name "*.csv" | head -20
```

### Errores comunes

| Error | Causa | Solución |
|-------|-------|----------|
| `Invalid cross-device link` | SourceMeter no está copiado al host | Ejecutar el paso 7 de instalación |
| `FindBugsTask: critical error` | No hay archivos `.class` compilados | Asegurarse de que `_runFB = 'false'` en `sourceMeter.py` |
| `TimeLimitExceeded(1200)` | Modo `auto` con timeout bajo | Cambiar `SCAT_MODE=development` en `.env` |
| `No se encontró directorio de análisis` | Ruta de resultados incorrecta | Verificar que la ruta en `_buscar_directorio_analisis` incluye `project_name` dos veces |

---

## 🏗️ Arquitectura

```
NexSCAT
├── Django (web)          → http://localhost:8000
├── Celery Worker         → Análisis paralelo SonarQube + SourceMeter
├── Redis                 → Broker de tareas Celery
├── PostgreSQL            → Base de datos (proyectos, métricas)
├── SonarQube             → http://localhost:9000
└── Flower                → http://localhost:5555 (monitor de tareas)
```

### Flujo de análisis

1. Usuario importa proyecto desde la interfaz web
2. Se lanzan en paralelo: tarea SonarQube + tarea SourceMeter (via Celery)
3. SonarQube analiza y guarda métricas a nivel proyecto
4. SourceMeter genera CSVs con métricas a nivel Package y Class
5. El sistema procesa los CSVs y guarda en PostgreSQL
6. El dashboard muestra métricas en tres niveles: Proyecto / Componente / Clase
