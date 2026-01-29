# main/tasks.py
"""
Tareas asíncronas de Celery para análisis paralelo de proyectos
"""
import logging
import time
from pathlib import Path
from celery import shared_task, group, chord
from celery.result import allow_join_result
from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from main.services.factory import sonar, source
from .models import Project

logger = logging.getLogger(__name__)

# ============================================
# CONSTANTES
# ============================================
EMOJI_SONAR = "🔵"
EMOJI_SOURCE = "🟢"
EMOJI_SUCCESS = "✅"
EMOJI_ERROR = "❌"
EMOJI_WARNING = "⚠️"
EMOJI_PARALLEL = "⚡"
EMOJI_START = "🚀"
EMOJI_FINISH = "🏁"


# ============================================
# UTILIDADES
# ============================================
def log_separator(char="=", length=70):
    """Imprime un separador visual"""
    print(f"\n{char * length}")


def log_header(title, emoji=""):
    """Imprime un header visual"""
    log_separator()
    print(f"{emoji} {title}")
    log_separator()


def log_step(step, total, message, emoji=""):
    """Imprime un paso del proceso"""
    print(f"[{step}/{total}] {emoji} {message}")


# ============================================
# TAREA DE PRUEBA
# ============================================
@shared_task(bind=True)
def test_celery(self):
    """Tarea de prueba simple para verificar que Celery funciona"""
    print("\n")
    log_header("🧪 TAREA DE PRUEBA DE CELERY", "🧪")
    print(f"Task ID: {self.request.id}")
    print("Esperando 2 segundos...")
    time.sleep(2)
    print(f"{EMOJI_SUCCESS} ¡Tarea de prueba completada!")
    log_separator()
    return "¡Celery funciona correctamente!"


# ============================================
# TAREAS INDIVIDUALES POR HERRAMIENTA
# ============================================

@shared_task(bind=True, max_retries=3)
def analizar_con_sonarqube(self, project_id: int, token: str):
    """
    Analiza un proyecto con SonarQube

    Args:
        project_id: ID del proyecto
        token: Token de autenticación de SonarQube

    Returns:
        dict: Resultado del análisis
    """
    task_id = self.request.id

    try:
        # Obtener proyecto con lock
        with transaction.atomic():
            project = Project.objects.select_for_update().get(id_project=project_id)
            project_name = project.name
            project_path = project.path
            project_key = sonar.normalizar_project_key(project_name)

        log_header(f"{EMOJI_SONAR} SONARQUBE: {project_name}", EMOJI_SONAR)
        print(f"Task ID: {task_id}")
        print(f"Project ID: {project_id}")
        print(f"Project Key: {project_key}")
        print(f"Path: {project_path}")

        # PASO 1: Ejecutar análisis
        log_step(1, 3, "Ejecutando análisis de SonarQube...", EMOJI_SONAR)
        start_time = time.time()

        scanner_path = settings.SONAR_SCANNER_PATH
        success, mensaje = sonar.analizar(scanner_path, project_path, token)

        elapsed = time.time() - start_time

        if not success:
            print(f"{EMOJI_ERROR} SonarQube falló: {mensaje}")
            print(f"Tiempo transcurrido: {elapsed:.1f}s")
            log_separator()
            raise Exception(f"SonarQube falló: {mensaje}")

        print(f"{EMOJI_SUCCESS} Análisis completado en {elapsed:.1f}s")

        # PASO 2: Esperar procesamiento
        log_step(2, 3, "Esperando procesamiento en servidor SonarQube...", EMOJI_SONAR)
        time.sleep(5)  # Dar tiempo al servidor

        # PASO 3: Procesar métricas
        log_step(3, 3, "Procesando y guardando métricas...", EMOJI_SONAR)
        process_start = time.time()

        with transaction.atomic():
            sonar.procesar_con_reintentos(project, token, project_key, max_reintentos=3)

        process_elapsed = time.time() - process_start
        total_elapsed = time.time() - start_time

        print(f"{EMOJI_SUCCESS} Métricas procesadas en {process_elapsed:.1f}s")
        print(f"{EMOJI_FINISH} SONARQUBE COMPLETADO - Tiempo total: {total_elapsed:.1f}s")
        log_separator()

        return {
            'success': True,
            'tool': 'SonarQube',
            'project_id': project_id,
            'project_name': project_name,
            'elapsed_time': total_elapsed,
            'message': mensaje
        }

    except Project.DoesNotExist:
        error_msg = f"Proyecto con ID {project_id} no existe"
        print(f"{EMOJI_ERROR} {error_msg}")
        log_separator()
        logger.error(error_msg)
        return {'success': False, 'tool': 'SonarQube', 'error': error_msg}

    except Exception as e:
        error_msg = str(e)
        print(f"{EMOJI_ERROR} Error en SonarQube: {error_msg}")
        log_separator()
        logger.error(f"Error en SonarQube para proyecto {project_id}: {error_msg}")

        # Retry automático si quedan intentos
        if self.request.retries < self.max_retries:
            print(f"{EMOJI_WARNING} Reintentando... (Intento {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e, countdown=60)

        return {'success': False, 'tool': 'SonarQube', 'error': error_msg}


@shared_task(bind=True, max_retries=3)
def analizar_con_sourcemeter(self, project_id: int):
    """
    Analiza un proyecto con SourceMeter

    Args:
        project_id: ID del proyecto

    Returns:
        dict: Resultado del análisis
    """
    task_id = self.request.id

    try:
        # Obtener proyecto con lock
        with transaction.atomic():
            project = Project.objects.select_for_update().get(id_project=project_id)
            project_name = project.name
            project_path = project.path
            project_key = sonar.normalizar_project_key(project_name)

        log_header(f"{EMOJI_SOURCE} SOURCEMETER: {project_name}", EMOJI_SOURCE)
        print(f"Task ID: {task_id}")
        print(f"Project ID: {project_id}")
        print(f"Project Key: {project_key}")
        print(f"Path: {project_path}")

        # PASO 1: Ejecutar análisis
        log_step(1, 2, "Ejecutando análisis de SourceMeter...", EMOJI_SOURCE)
        start_time = time.time()

        success, mensaje = source.analizar(project_path, project_key, project_name)

        elapsed = time.time() - start_time

        if not success:
            print(f"{EMOJI_WARNING} SourceMeter: {mensaje}")
            print(f"Tiempo transcurrido: {elapsed:.1f}s")
            log_separator()
            # SourceMeter no es crítico, retornar warning
            return {
                'success': False,
                'tool': 'SourceMeter',
                'project_id': project_id,
                'project_name': project_name,
                'elapsed_time': elapsed,
                'warning': mensaje
            }

        print(f"{EMOJI_SUCCESS} Análisis completado en {elapsed:.1f}s")

        # PASO 2: Procesar métricas
        log_step(2, 2, "Procesando y guardando métricas...", EMOJI_SOURCE)
        process_start = time.time()

        with transaction.atomic():
            source.procesar(project, project_key)

        process_elapsed = time.time() - process_start
        total_elapsed = time.time() - start_time

        print(f"{EMOJI_SUCCESS} Métricas procesadas en {process_elapsed:.1f}s")
        print(f"{EMOJI_FINISH} SOURCEMETER COMPLETADO - Tiempo total: {total_elapsed:.1f}s")
        log_separator()

        return {
            'success': True,
            'tool': 'SourceMeter',
            'project_id': project_id,
            'project_name': project_name,
            'elapsed_time': total_elapsed,
            'message': mensaje
        }

    except Project.DoesNotExist:
        error_msg = f"Proyecto con ID {project_id} no existe"
        print(f"{EMOJI_ERROR} {error_msg}")
        log_separator()
        logger.error(error_msg)
        return {'success': False, 'tool': 'SourceMeter', 'error': error_msg}

    except Exception as e:
        error_msg = str(e)
        print(f"{EMOJI_ERROR} Error en SourceMeter: {error_msg}")
        log_separator()
        logger.error(f"Error en SourceMeter para proyecto {project_id}: {error_msg}")

        # Retry automático si quedan intentos
        if self.request.retries < self.max_retries:
            print(f"{EMOJI_WARNING} Reintentando... (Intento {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e, countdown=60)

        return {'success': False, 'tool': 'SourceMeter', 'error': error_msg}


# ============================================
# TAREA COORDINADORA - ANÁLISIS PARALELO
# ============================================

@shared_task(bind=True)
def analizar_proyecto_paralelo(self, project_id: int, token: str):
    """
    Coordina el análisis PARALELO de un proyecto con ambas herramientas

    Esta tarea lanza SonarQube y SourceMeter AL MISMO TIEMPO usando group()

    Args:
        project_id: ID del proyecto
        token: Token de SonarQube

    Returns:
        dict: Resultados combinados de ambas herramientas
    """
    task_id = self.request.id

    try:
        # Obtener info del proyecto
        project = Project.objects.get(id_project=project_id)
        project_name = project.name

        log_header(f"{EMOJI_PARALLEL} ANÁLISIS PARALELO: {project_name}", EMOJI_PARALLEL)
        print(f"Coordinator Task ID: {task_id}")
        print(f"Project ID: {project_id}")
        print(f"🔵 SonarQube y 🟢 SourceMeter se ejecutarán EN PARALELO")
        log_separator()

        # Actualizar estado inicial
        self.update_state(
            state='PROGRESS',
            meta={
                'current_step': 1,
                'total_steps': 3,
                'status': f'Iniciando análisis paralelo de {project_name}...',
                'percent': 10,
                'mode': 'parallel'
            }
        )

        # 🔥 EJECUTAR EN PARALELO usando group()
        print(f"\n{EMOJI_START} LANZANDO TAREAS EN PARALELO...")
        print("=" * 70)

        analysis_group = group(
            analizar_con_sonarqube.s(project_id, token),
            analizar_con_sourcemeter.s(project_id)
        )

        # Ejecutar y esperar resultados
        start_time = time.time()
        result = analysis_group.apply_async()

        print(f"{EMOJI_PARALLEL} 2 tareas lanzadas simultáneamente:")
        print(f"  {EMOJI_SONAR} SonarQube (Task ID: {result.results[0].id})")
        print(f"  {EMOJI_SOURCE} SourceMeter (Task ID: {result.results[1].id})")
        print("=" * 70)

        # Actualizar estado
        self.update_state(
            state='PROGRESS',
            meta={
                'current_step': 2,
                'total_steps': 3,
                'status': f'Analizando {project_name} con ambas herramientas...',
                'percent': 50,
                'mode': 'parallel',
                'sonar_task_id': result.results[0].id,
                'source_task_id': result.results[1].id
            }
        )

        # Esperar a que AMBAS terminen
        print(f"\n⏳ Esperando a que ambas herramientas terminen...")

        with allow_join_result():
            results = result.get(timeout=settings.ANALYSIS_TIMEOUT)

        elapsed_total = time.time() - start_time

        # Procesar resultados
        sonar_result = results[0]
        source_result = results[1]

        log_header(f"{EMOJI_FINISH} RESULTADOS DEL ANÁLISIS PARALELO", EMOJI_FINISH)
        print(f"Proyecto: {project_name}")
        print(f"Tiempo total: {elapsed_total:.1f}s")
        print(f"\n{EMOJI_SONAR} SonarQube:")
        print(f"  Estado: {EMOJI_SUCCESS if sonar_result.get('success') else EMOJI_ERROR}")
        print(f"  Tiempo: {sonar_result.get('elapsed_time', 0):.1f}s")

        print(f"\n{EMOJI_SOURCE} SourceMeter:")
        print(f"  Estado: {EMOJI_SUCCESS if source_result.get('success') else EMOJI_WARNING}")
        print(f"  Tiempo: {source_result.get('elapsed_time', 0):.1f}s")

        # Calcular speedup
        sonar_time = sonar_result.get('elapsed_time', 0)
        source_time = source_result.get('elapsed_time', 0)
        sequential_time = sonar_time + source_time
        speedup = sequential_time / elapsed_total if elapsed_total > 0 else 1

        print(f"\n{EMOJI_PARALLEL} BENEFICIO DEL PARALELISMO:")
        print(f"  Tiempo secuencial estimado: {sequential_time:.1f}s")
        print(f"  Tiempo paralelo real: {elapsed_total:.1f}s")
        print(f"  Speedup: {speedup:.2f}x más rápido")
        print(f"  Ahorro de tiempo: {sequential_time - elapsed_total:.1f}s")
        log_separator()

        # Actualizar estado final
        self.update_state(
            state='PROGRESS',
            meta={
                'current_step': 3,
                'total_steps': 3,
                'status': f'Análisis completado para {project_name}',
                'percent': 100,
                'mode': 'parallel'
            }
        )

        return {
            'success': sonar_result.get('success', False),
            'project_id': project_id,
            'project_name': project_name,
            'mode': 'parallel',
            'sonar_result': sonar_result,
            'source_result': source_result,
            'total_time': elapsed_total,
            'speedup': speedup,
            'time_saved': sequential_time - elapsed_total
        }

    except Exception as e:
        error_msg = f"Error en análisis paralelo: {str(e)}"
        print(f"\n{EMOJI_ERROR} {error_msg}")
        log_separator()
        logger.error(error_msg)

        import traceback
        traceback.print_exc()

        return {
            'success': False,
            'project_id': project_id,
            'error': error_msg,
            'mode': 'parallel'
        }


# ============================================
# TAREA COMPLETA (COMPATIBILIDAD)
# ============================================

@shared_task(bind=True)
def analizar_proyecto_completo(self, proyecto_path: str, usuario_id: int, token: str):
    """
    Tarea compatible con el código existente
    Decide si usar paralelo o secuencial según configuración
    """
    try:
        # Crear proyecto
        proyecto_path = Path(proyecto_path)
        project_key = sonar.normalizar_project_key(proyecto_path.name)

        user = User.objects.get(id=usuario_id)

        with transaction.atomic():
            project, created = Project.objects.update_or_create(
                key=project_key,
                defaults={
                    'name': proyecto_path.name,
                    'path': str(proyecto_path),
                    'created_by': user
                }
            )

        # Decidir modo según configuración
        if settings.ANALYSIS_CONFIG.ENABLE_PARALLEL:
            # Modo paralelo
            return analizar_proyecto_paralelo(project.id_project, token)
        else:
            # Modo secuencial (lógica existente)
            return _analizar_proyecto_logica(
                str(proyecto_path),
                usuario_id,
                token,
                progress_callback=lambda step, msg, pct: self.update_state(
                    state='PROGRESS',
                    meta={'current_step': step, 'total_steps': 5, 'status': msg, 'percent': pct}
                )
            )

    except Exception as e:
        logger.error(f"Error en analizar_proyecto_completo: {str(e)}")
        return {'success': False, 'error': str(e)}


# ============================================
# LÓGICA SECUENCIAL (FALLBACK)
# ============================================

def _analizar_proyecto_logica(proyecto_path: str, usuario_id: int, token: str, progress_callback=None):
    """
    Lógica secuencial de análisis (modo sin paralelismo)
    Se mantiene para compatibilidad y cuando Celery no está disponible
    """

    def update_progress(step, message, percent):
        print(f"[{percent}%] {message}")
        if progress_callback:
            progress_callback(step, message, percent)

    try:
        from .models import Project

        proyecto_path = Path(proyecto_path)
        project_key = sonar.normalizar_project_key(proyecto_path.name)

        update_progress(1, f"Inicializando proyecto {proyecto_path.name}...", 5)

        user = User.objects.get(id=usuario_id)

        with transaction.atomic():
            project, created = Project.objects.update_or_create(
                key=project_key,
                defaults={
                    'name': proyecto_path.name,
                    'path': str(proyecto_path),
                    'created_by': user
                }
            )

        update_progress(1, "Proyecto listo para análisis", 20)

        # SonarQube
        update_progress(2, "Ejecutando análisis de SonarQube...", 25)

        scanner_path = settings.SONAR_SCANNER_PATH
        success_sonar, mensaje_sonar = sonar.analizar(scanner_path, str(proyecto_path), token)

        if success_sonar:
            update_progress(2, "SonarQube completado, procesando métricas...", 50)
            with transaction.atomic():
                sonar.procesar_con_reintentos(project, token, project_key, max_reintentos=3)
            update_progress(2, "Métricas de SonarQube guardadas", 60)
        else:
            update_progress(2, f"Error en SonarQube: {mensaje_sonar}", 30)
            return {'success': False, 'error': f'SonarQube: {mensaje_sonar}'}

        # SourceMeter
        update_progress(3, "Ejecutando análisis de SourceMeter...", 65)

        success_source, mensaje_source = source.analizar(str(proyecto_path), project_key, proyecto_path.name)

        if success_source:
            update_progress(3, "SourceMeter completado, procesando métricas...", 75)
            with transaction.atomic():
                source.procesar(project, project_key)
            update_progress(3, "Métricas de SourceMeter guardadas", 90)
        else:
            update_progress(3, f"Advertencia en SourceMeter: {mensaje_source}", 85)

        update_progress(5, "¡Análisis completado exitosamente!", 100)

        return {
            'success': True,
            'project_name': proyecto_path.name,
            'project_id': project.id_project,
            'mode': 'sequential',
            'sonar_success': success_sonar,
            'source_success': success_source
        }

    except Exception as e:
        logger.error(f"Error en análisis secuencial: {str(e)}")
        return {'success': False, 'error': str(e)}