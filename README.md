# NexSCAT — Nexus Source Code Analysis Tool

> Plataforma web para el análisis estático de un lote de proyectos Java.  
> Integra **SonarQube** y **SourceMeter** en una única interfaz, con exportación de métricas en CSV, XML y JSON.

**Universidad Nacional del Nordeste — Proyecto Final de Carrera, 2026**  
Autora: Celeste María Luz Ojeda Rodríguez

---

## 🌐 Demo en vivo

NexSCAT está desplegado y accesible en:

**[https://nexscat.com](https://nexscat.com)**

No es necesario instalar nada para explorarlo. Las instrucciones de instalación local a continuación son para quienes deseen ejecutar el sistema en su propio entorno.

---

## Índice

- [Descripción](#descripción)
- [Arquitectura](#arquitectura)
- [Requisitos](#requisitos)
- [Instalación local](#instalación-local)
- [Despliegue cloud](#despliegue-cloud)
- [Configuración](#configuración)
- [Uso](#uso)
- [Comandos útiles](#comandos-útiles)
- [Reiniciar análisis](#reiniciar-análisis)
- [Diagnóstico de errores](#diagnóstico-de-errores)

---

## Descripción

NexSCAT automatiza el análisis estático de lotes de proyectos Java combinando dos herramientas complementarias:

- **SonarQube** — detecta vulnerabilidades, code smells y métricas de mantenibilidad y seguridad.
- **SourceMeter** — calcula métricas detalladas de complejidad, acoplamiento, cohesión y herencia.

Los análisis se ejecutan en paralelo mediante Celery, los resultados se almacenan en PostgreSQL y se visualizan en un dashboard web con navegación jerárquica por Proyecto → Componente → Clase.

---

## Arquitectura

```
                        ┌─────────────┐
                        │  Navegador  │
                        └──────┬──────┘
                               │ HTTPS
                        ┌──────▼──────┐
                        │ Cloudflare  │  DNS + SSL/TLS + DDoS  [solo cloud]
                        └──────┬──────┘
                               │ HTTP (interno)
                        ┌──────▼──────┐
                        │    Nginx    │  proxy inverso + archivos estáticos
                        └──────┬──────┘
                               │
                        ┌──────▼──────┐
                        │   Django    │  lógica de negocio + vistas
                        └──────┬──────┘
               ┌───────────────┼───────────────┐
        ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
        │    Redis    │ │ PostgreSQL  │ │  SonarQube  │
        │   (broker)  │ │    (BD)     │ │  (análisis) │
        └──────┬──────┘ └─────────────┘ └─────────────┘
               │
        ┌──────▼──────┐
        │Celery Worker│  ejecuta SonarQube + SourceMeter en paralelo
        └─────────────┘

  En entorno local: el Navegador conecta directo a Nginx por HTTP (sin Cloudflare).
```

**Flujo de análisis:**
1. El usuario importa proyectos (ZIP o repositorio GitHub) desde la interfaz web
2. Django encola una tarea Celery por herramienta (SonarQube + SourceMeter en paralelo)
3. SonarQube analiza vía `sonar-scanner` y expone métricas por su API REST
4. SourceMeter genera archivos CSV con métricas a nivel Package, Class y Method
5. El sistema procesa y persiste todo en PostgreSQL
6. El dashboard muestra métricas en tres niveles con opción de exportación

---

## Requisitos

### Sistema operativo

> ⚠️ **NexSCAT requiere Linux nativo o VM Linux.**  
> SourceMeter necesita que sus binarios y el directorio de resultados estén en el **mismo filesystem**.  
> En Windows con Docker Desktop o WSL2 esto no es posible por la separación entre el overlay de Docker y los bind mounts del host, lo que produce el error `Invalid cross-device link`.  
> Se recomienda **Ubuntu 22.04 o 24.04**.

### Software requerido

| Herramienta | Versión mínima |
|-------------|---------------|
| Docker Engine | 24.0 |
| Docker Compose | 2.0 |
| Git | 2.33 |
| Git LFS | cualquiera |

> ⚠️ Usar **Docker Engine**, no Docker Desktop.

### Hardware recomendado

| Recurso | Mínimo |
|---------|--------|
| RAM | 8 GB |
| Disco | 20 GB libres |
| CPU | 2+ núcleos |

---

## Instalación local

### 1. Instalar Docker Engine

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# En Ubuntu 25.04: usar repositorio 'noble' (24.04) por compatibilidad
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu noble stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Ejecutar Docker sin sudo
sudo usermod -aG docker $USER
newgrp docker
```

### 2. Instalar Git LFS

```bash
sudo apt-get install git-lfs
git lfs install
```

### 3. Clonar el repositorio

```bash
git clone https://github.com/CelesteOj22/nexscat.git
cd nexscat
```

Git LFS descargará automáticamente el binario de SourceMeter (~384 MB) durante el clonado.

### 4. Configurar variables de entorno

```bash
cp .env.example .env
```

Editá `.env` con tus valores. Mínimo requerido:

```env
DB_PASSWORD=tu_password
SECRET_KEY=tu_secret_key
SONARQUBE_TOKEN=        # se completa en el paso 6
SCAT_MODE=development
```

Para generar el `SECRET_KEY`:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

### 5. Crear directorios necesarios

```bash
mkdir -p ~/nexscat/sm_results
mkdir -p ~/nexscat/proyectos
mkdir -p ~/nexscat/tools
```

### 6. Levantar los servicios

```bash
docker compose -f docker-compose.local.yml up -d
```

La primera vez puede tardar varios minutos mientras Docker descarga y construye las imágenes. Para verificar que todos los servicios estén activos:

```bash
docker compose -f docker-compose.local.yml ps
```

### 7. Configurar SonarQube

1. Accedé a [http://localhost:9000](http://localhost:9000)
2. Login inicial: `admin` / `admin` → cambiá la contraseña cuando lo pida
3. Ir a: **My Account → Security → Generate Token**
4. Copiá el token y actualizá `.env`:
   ```env
   SONARQUBE_TOKEN=squ_xxxxxxxxxxxxxxxxxxxxxxxx
   ```
5. Reiniciá los contenedores:
   ```bash
   docker compose -f docker-compose.local.yml restart
   ```

### 8. Copiar SourceMeter al host

> ⚠️ **Este paso es obligatorio.** Sin él, SourceMeter fallará con `Invalid cross-device link`.

SourceMeter necesita que sus binarios y el directorio de resultados estén en el mismo filesystem. Al copiarlo al host, `/opt/tools/sourcemeter` y `/opt/sm_results` quedan en el filesystem nativo de Ubuntu.

```bash
# Asegurarse de que el worker esté corriendo
docker compose -f docker-compose.local.yml up -d celery_worker

# Copiar SourceMeter al host
docker cp nexscat_celery_local:/opt/tools/sourcemeter ~/nexscat/tools/sourcemeter

# Reiniciar para aplicar el bind mount
docker compose -f docker-compose.local.yml restart celery_worker web
```

### 9. Verificar acceso

| Servicio | URL |
|----------|-----|
| Aplicación NexSCAT | http://localhost:8000 |
| Panel SonarQube | http://localhost:9000 |
| Monitor Celery (Flower) | http://localhost:5555 |

---

## Despliegue cloud

NexSCAT incluye un perfil de composición específico para producción (`docker-compose.cloud.yml`) que agrega Nginx como proxy inverso. El stack fue desplegado en una instancia **Hetzner CPX42** (Ubuntu 22.04 LTS) con el dominio **nexscat.com** gestionado a través de **Cloudflare** (DNS + SSL/TLS + protección DDoS).

### Requisitos adicionales

- Instancia Linux con al menos 16 GB de RAM (la CPX42 de Hetzner cubre los requisitos con holgura)
- Acceso SSH a la instancia
- Docker Engine, Docker Compose y Git LFS instalados (mismos pasos que en la instalación local)

### Procedimiento

```bash
# 1. Clonar el repositorio en el servidor (con LFS)
git clone https://github.com/CelesteOj22/nexscat.git
cd nexscat

# 2. Configurar variables de producción en .env
#    Incluir ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, DEBUG=False, etc.

# 3. Levantar el stack de producción
docker compose -f docker-compose.cloud.yml up --build -d
```

Una vez desplegado, la aplicación queda accesible en **https://nexscat.com**.  
Los servicios internos (SonarQube, Flower, PostgreSQL) no están expuestos públicamente y pueden consultarse mediante túneles SSH si es necesario.

---

## Configuración

### Variables de entorno

| Variable | Descripción | Valor por defecto |
|----------|-------------|-------------------|
| `DB_PASSWORD` | Contraseña de PostgreSQL | `1234` |
| `SECRET_KEY` | Clave secreta de Django | (requerido) |
| `SONARQUBE_TOKEN` | Token de autenticación SonarQube | (requerido) |
| `DEBUG` | Modo debug de Django | `True` |
| `SCAT_MODE` | Modo de análisis | `development` |
| `MAX_PARALLEL_ANALYSIS` | Análisis simultáneos máximos | `2` |

### Modos de análisis (`SCAT_MODE`)

| Modo | Descripción | Timeout |
|------|-------------|---------|
| `development` | Local con recursos moderados | 7200s (2h) |
| `production` | Cloud / recursos limitados | 7200s (2h) |
| `balanced` | Balance rendimiento/recursos | 7200s (2h) |
| `performance` | Máximo rendimiento local | 1800s (30min) |
| `auto` | Detección automática ⚠️ | variable |

> ⚠️ Evitá el modo `auto` si tus proyectos tardan más de 20 minutos en analizarse. Puede reducir el timeout a 1200s.

---

## Uso

### Agregar proyectos para analizar

Los proyectos Java deben ubicarse en la carpeta `proyectos/`:

```bash
# Copiar un proyecto manualmente
cp -r /ruta/al/proyecto ~/nexscat/proyectos/nombre-proyecto-1.0

# Desde carpeta compartida de VirtualBox
rsync -av --progress /media/sf_nombre_carpeta/ ~/nexscat/proyectos/
```

> `rsync` es recomendable para copias grandes: si se interrumpe, retoma desde donde quedó sin recopiar archivos ya transferidos.

La estructura esperada es:

```
~/nexscat/proyectos/
├── proyecto-a-1.0/
│   ├── src/
│   ├── pom.xml / build.xml
│   └── ...
├── proyecto-b-2.3/
└── ...
```

Desde la interfaz web importás el proyecto con la ruta `/app/proyectos/nombre-proyecto-1.0`.

---

## Comandos útiles

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

## Reiniciar análisis

Para borrar todos los datos de análisis y empezar desde cero:

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

## Diagnóstico de errores

### Ver estado general del análisis

```bash
docker compose -f docker-compose.local.yml logs celery_worker --tail=200 | \
  grep -E "✅|❌|⚠️|critical error|succeeded|failed"
```

### Errores comunes

| Error | Causa | Solución |
|-------|-------|----------|
| `Invalid cross-device link` | SourceMeter no copiado al host | Ejecutar el [paso 8](#8-copiar-sourcemeter-al-host) |
| `FindBugsTask: critical error` | No hay archivos `.class` compilados | Verificar que `_runFB = 'false'` en `sourceMeter.py` |
| `TimeLimitExceeded(1200)` | Modo `auto` con timeout bajo | Cambiar a `SCAT_MODE=development` en `.env` |
| `No se encontró directorio de análisis` | Ruta de resultados incorrecta | Verificar que la ruta en `_buscar_directorio_analisis` incluye `project_name` dos veces |

### Comandos de diagnóstico específicos

```bash
# Error de SourceMeter
docker compose -f docker-compose.local.yml logs celery_worker --tail=200 | \
  grep -A 10 "DirectoryBasedAnalysisTask"

# Timeout de tareas
docker compose -f docker-compose.local.yml logs celery_worker --tail=100 | \
  grep -E "TimeLimitExceeded|time limit|TIMEOUT"

# Ver CSVs generados por SourceMeter
find ~/nexscat/sm_results -name "*.csv" | head -20
```
