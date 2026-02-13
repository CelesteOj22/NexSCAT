# NexSCAT - Nexus Source Code Analysis Tool

## 🚀 Instalación

### Prerrequisitos
- Docker Desktop
- Git

### Pasos de instalación

1. **Clonar el repositorio**
```bash
   git clone https://github.com/CelesteOj22/nexscat.git
   cd nexscat
```

2. **Configurar variables de entorno**
```bash
   # Copiar el archivo de ejemplo
   cp .env.example .env
   
   # Editar .env con tus valores
   # Mínimo requerido: DB_PASSWORD, SECRET_KEY, SONARQUBE_TOKEN
```

3. **Generar SECRET_KEY de Django**
```bash
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```
   Copia el resultado en `.env` como `SECRET_KEY`

4. **Levantar los contenedores**
```bash
   docker-compose up --build
```

5. **Configurar SonarQube (primera vez)**
   - Acceder a http://localhost:9000
   - Login: `admin` / `admin` (cambiar contraseña)
   - Ir a: **My Account → Security → Generate Token**
   - Copiar el token y agregarlo a `.env` como `SONARQUBE_TOKEN`
   - Reiniciar contenedores: `docker-compose restart`

6. **Acceder a NexSCAT**
   - Aplicación: http://localhost:8000
   - SonarQube: http://localhost:9000

## ⚙️ Configuración

### Variables de entorno importantes

| Variable | Descripción | Valor por defecto |
|----------|-------------|-------------------|
| `DB_PASSWORD` | Contraseña de PostgreSQL | `1234` |
| `SECRET_KEY` | Clave secreta de Django | (requerido) |
| `SONARQUBE_TOKEN` | Token de autenticación SonarQube | (requerido) |
| `DEBUG` | Modo debug de Django | `True` |
| `MAX_PARALLEL_ANALYSIS` | Análisis simultáneos | `2` |

Ver `.env.example` para todas las opciones disponibles.

## 🐳 Comandos Docker útiles
```bash
# Ver logs
docker-compose logs -f web

# Reiniciar servicios
docker-compose restart

# Detener todo
docker-compose down

# Limpiar volúmenes (⚠️ elimina datos)
docker-compose down -v
```
