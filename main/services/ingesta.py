# main/services/ingesta.py
"""
Módulo de ingesta de proyectos para deploy en nube.
Reemplaza el mecanismo de path local por ZIP upload y clone de GitHub.
"""
import os
import shutil
import subprocess
import zipfile
import logging
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

# Directorio base donde se guardan los proyectos en el servidor
# Definir en settings.py: PROYECTOS_DIR = '/app/proyectos'
def get_proyectos_dir() -> Path:
    proyectos_dir = Path(getattr(settings, 'PROYECTOS_DIR', '/app/proyectos'))
    proyectos_dir.mkdir(parents=True, exist_ok=True)
    return proyectos_dir


def ingesta_zip(zip_file) -> tuple[bool, str, Path | None]:
    """
    Recibe un archivo ZIP subido, lo descomprime y devuelve el path del proyecto.

    Args:
        zip_file: InMemoryUploadedFile de Django (request.FILES['zip_file'])

    Returns:
        (success, mensaje, project_path)
    """
    try:
        zip_name = Path(zip_file.name).stem  # nombre sin .zip
        destino = get_proyectos_dir() / zip_name

        # Si ya existe, limpiar para re-analizar
        if destino.exists():
            shutil.rmtree(destino)

        destino.mkdir(parents=True, exist_ok=True)

        logger.info(f"Descomprimiendo {zip_file.name} en {destino}")

        with zipfile.ZipFile(zip_file, 'r') as zf:
            # Seguridad: evitar path traversal
            for member in zf.namelist():
                member_path = Path(member)
                if member_path.is_absolute() or '..' in member_path.parts:
                    return False, f"El ZIP contiene rutas inseguras: {member}", None

            zf.extractall(destino)

        # Si el ZIP descomprimió una sola carpeta raíz, usar esa como proyecto
        contents = [p for p in destino.iterdir()]
        if len(contents) == 1 and contents[0].is_dir():
            project_path = contents[0]
        else:
            project_path = destino

        logger.info(f"ZIP descomprimido exitosamente en {project_path}")
        return True, "ZIP descomprimido exitosamente", project_path

    except zipfile.BadZipFile:
        return False, "El archivo no es un ZIP válido", None
    except Exception as e:
        logger.error(f"Error procesando ZIP: {e}")
        return False, f"Error al procesar el ZIP: {str(e)}", None


def ingesta_github(repo_url: str, branch: str = None) -> tuple[bool, str, Path | None]:
    """
    Clona un repositorio de GitHub y devuelve el path del proyecto.

    Args:
        repo_url: URL del repositorio (ej: https://github.com/usuario/repo)
        branch: Rama a clonar (None = rama por defecto)

    Returns:
        (success, mensaje, project_path)
    """
    try:
        # Extraer nombre del repo desde la URL
        repo_name = repo_url.rstrip('/').split('/')[-1]
        if repo_name.endswith('.git'):
            repo_name = repo_name[:-4]

        destino = get_proyectos_dir() / repo_name

        # Si ya existe, limpiar para re-clonar
        if destino.exists():
            shutil.rmtree(destino)

        logger.info(f"Clonando {repo_url} en {destino}")

        comando = ['git', 'clone', '--depth', '1']  # shallow clone para velocidad
        if branch:
            comando.extend(['-b', branch])
        comando.extend([repo_url, str(destino)])

        result = subprocess.run(
            comando,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            timeout=300  # 5 minutos máximo para clonar
        )

        if result.returncode != 0:
            error_detail = result.stdout[-500:] if result.stdout else "sin detalles"
            logger.error(f"git clone falló: {error_detail}")

            if 'Repository not found' in result.stdout or '404' in result.stdout:
                return False, "Repositorio no encontrado. Verificá que la URL sea correcta y el repo sea público.", None
            elif 'Connection refused' in result.stdout or 'Could not resolve' in result.stdout:
                return False, "No se pudo conectar con GitHub. Verificá la URL.", None
            else:
                return False, f"Error al clonar el repositorio: {error_detail}", None

        logger.info(f"Repositorio clonado exitosamente en {destino}")
        return True, f"Repositorio '{repo_name}' clonado exitosamente", destino

    except subprocess.TimeoutExpired:
        return False, "El clonado tardó demasiado (más de 5 minutos). El repositorio puede ser muy grande.", None
    except FileNotFoundError:
        return False, "git no está instalado en el servidor.", None
    except Exception as e:
        logger.error(f"Error clonando repositorio: {e}")
        return False, f"Error inesperado al clonar: {str(e)}", None


def limpiar_proyecto(project_path: Path):
    """
    Elimina el directorio del proyecto del servidor luego del análisis.
    Llamar después de que SourceMeter y SonarQube terminen.
    """
    try:
        if project_path and project_path.exists():
            shutil.rmtree(project_path)
            logger.info(f"Proyecto limpiado: {project_path}")
    except Exception as e:
        logger.warning(f"No se pudo limpiar {project_path}: {e}")
