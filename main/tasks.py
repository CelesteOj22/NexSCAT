# tasks.py
import logging
from pathlib import Path
from celery import shared_task
from django.conf import settings
from django.contrib.auth.models import User

from main.services.factory import sonar, source

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def test_celery(self):
    """
    Tarea de prueba simple para verificar que Celery funciona
    """
    print("🧪 Tarea de prueba de Celery ejecutándose...")
    import time
    time.sleep(2)
    print("✅ Tarea de prueba completada")
    return "¡Celery funciona correctamente!"


@shared_task(bind=True)
def analizar_proyecto_completo(self, proyecto_path: str, usuario_id: int, token: str):
    """
    Tarea de Celery con reporte de progreso en tiempo real
    """
    try:
        # 🔄 Estado inicial
        self.update_state(
            state='PROGRESS',
            meta={
                'current_step': 1,
                'total_steps': 5,
                'status': 'Verificando herramientas...',
                'percent': 10
            }
        )

        logger.info(f"🚀 Tarea Celery iniciada para: {proyecto_path}")

        # Llamar a la lógica con callback de progreso
        resultado = _analizar_proyecto_logica(
            proyecto_path,
            usuario_id,
            token,
            progress_callback=lambda step, message, percent: self.update_state(
                state='PROGRESS',
                meta={
                    'current_step': step,
                    'total_steps': 5,
                    'status': message,
                    'percent': percent
                }
            )
        )

        logger.info(f"✅ Tarea Celery completada para: {proyecto_path}")
        return resultado

    except Exception as e:
        logger.error(f"❌ Error en tarea Celery: {str(e)}")
        raise


def _analizar_proyecto_logica(proyecto_path: str, usuario_id: int, token: str, progress_callback=None):
    """
    Lógica real del análisis con callback opcional para progreso

    Args:
        progress_callback: función(step, message, percent) para reportar progreso
    """

    def update_progress(step, message, percent):
        """Helper para actualizar progreso"""
        print(f"[{percent}%] {message}")
        if progress_callback:
            progress_callback(step, message, percent)

    try:
        from .models import Project

        proyecto_path = Path(proyecto_path)
        project_key = sonar.normalizar_project_key(proyecto_path.name)

        # 📊 PASO 1: Inicialización (0-20%)
        update_progress(1, f"Inicializando proyecto {proyecto_path.name}...", 5)

        print(f"\n{'=' * 60}")
        print(f"📊 ANALIZANDO: {proyecto_path.name}")
        print(f"🔑 Project Key: {project_key}")
        print(f"{'=' * 60}\n")

        user = User.objects.get(id=usuario_id)

        update_progress(1, "Creando registro de proyecto...", 15)

        project, created = Project.objects.update_or_create(
            key=project_key,
            defaults={
                'name': proyecto_path.name,
                'path': str(proyecto_path),
                'created_by': user
            }
        )

        if created:
            print(f"✨ Proyecto creado: {project.name} (ID: {project.id_project})")
        else:
            print(f"🔄 Proyecto existente: {project.name} (ID: {project.id_project})")

        update_progress(1, "Proyecto listo para análisis", 20)

        # 📊 PASO 2: Análisis SonarQube (20-60%)
        print("\n" + "=" * 60)
        print("🔍 FASE 1: Análisis con SonarQube")
        print("=" * 60)

        update_progress(2, "Ejecutando análisis de SonarQube...", 25)

        scanner_path = settings.SONAR_SCANNER_PATH
        success_sonar, mensaje_sonar = sonar.analizar(
            scanner_path,
            str(proyecto_path),
            token
        )

        if success_sonar:
            print("✅ SonarQube: Análisis completado exitosamente")
            update_progress(2, "SonarQube completado, esperando procesamiento...", 45)

            print("📊 Procesando métricas de SonarQube...")
            update_progress(2, "Procesando métricas de SonarQube...", 50)

            sonar.procesar_con_reintentos(
                project,
                token,
                project_key,
                max_reintentos=3
            )

            print("✅ SonarQube: Métricas procesadas y guardadas")
            update_progress(2, "Métricas de SonarQube guardadas", 60)
        else:
            print(f"❌ SonarQube falló: {mensaje_sonar}")
            update_progress(2, f"Error en SonarQube: {mensaje_sonar}", 30)
            logger.error(f"Error en SonarQube para {project.name}: {mensaje_sonar}")
            return {
                'success': False,
                'project_name': proyecto_path.name,
                'error': f'SonarQube: {mensaje_sonar}',
                'sonar_success': False,
                'source_success': False
            }

        # 📊 PASO 3: Análisis SourceMeter (60-90%)
        print("\n" + "=" * 60)
        print("🔍 FASE 2: Análisis con SourceMeter")
        print("=" * 60)

        update_progress(3, "Ejecutando análisis de SourceMeter...", 65)

        success_source, mensaje_source = source.analizar(
            str(proyecto_path),
            project_key,
            proyecto_path.name
        )

        if success_source:
            print("✅ SourceMeter: Análisis completado exitosamente")
            update_progress(3, "SourceMeter completado, procesando métricas...", 75)

            print("📊 Procesando métricas de SourceMeter...")

            source.procesar(project, project_key)

            print("✅ SourceMeter: Métricas procesadas y guardadas")
            update_progress(3, "Métricas de SourceMeter guardadas", 90)
        else:
            print(f"⚠️ SourceMeter: {mensaje_source}")
            update_progress(3, f"Advertencia en SourceMeter: {mensaje_source}", 85)
            logger.warning(f"Error en SourceMeter para {project.name}: {mensaje_source}")

        # 📊 PASO 4: Finalización (90-100%)
        update_progress(4, "Guardando resultados finales...", 95)

        print(f"\n{'=' * 60}")
        print(f"✅ ANÁLISIS COMPLETADO: {proyecto_path.name}")
        print(f"   🔹 SonarQube: {'✅ OK' if success_sonar else '❌ Error'}")
        print(f"   🔹 SourceMeter: {'✅ OK' if success_source else '⚠️ Warning'}")
        print(f"{'=' * 60}\n")

        update_progress(5, "¡Análisis completado exitosamente!", 100)

        return {
            'success': True,
            'project_name': proyecto_path.name,
            'project_id': project.id_project,
            'sonar_success': success_sonar,
            'source_success': success_source,
            'mensaje_sonar': mensaje_sonar,
            'mensaje_source': mensaje_source
        }

    except User.DoesNotExist:
        error_msg = f"Usuario con ID {usuario_id} no existe"
        print(f"\n❌ ERROR: {error_msg}")
        update_progress(0, f"Error: {error_msg}", 0)
        logger.error(error_msg)
        return {
            'success': False,
            'project_name': proyecto_path.name if isinstance(proyecto_path, Path) else proyecto_path,
            'error': error_msg
        }

    except Exception as e:
        error_msg = f"Error general: {str(e)}"
        print(f"\n❌ ERROR GENERAL: {error_msg}")
        update_progress(0, error_msg, 0)
        logger.error(error_msg)

        import traceback
        traceback.print_exc()

        return {
            'success': False,
            'project_name': proyecto_path.name if isinstance(proyecto_path, Path) else proyecto_path,
            'error': str(e)
        }

@shared_task(bind=True)
def analizar_sonar(self, project_id: int, token: str):
    """
    Tarea específica para análisis solo con SonarQube
    """
    try:
        from .models import Project

        project = Project.objects.get(id_project=project_id)
        print(f"\n🔍 Analizando con SonarQube: {project.name}")

        scanner_path = settings.SONAR_SCANNER_PATH
        success, mensaje = sonar.analizar(
            scanner_path,
            project.path,
            token
        )

        if success:
            project_key = sonar.normalizar_project_key(project.name)
            sonar.procesar_con_reintentos(project, token, project_key, max_reintentos=3)
            print(f"✅ SonarQube completado para {project.name}")
            return {'success': True, 'message': mensaje}
        else:
            print(f"❌ SonarQube falló para {project.name}: {mensaje}")
            return {'success': False, 'error': mensaje}

    except Exception as e:
        error_msg = f"Error en análisis SonarQube: {str(e)}"
        print(f"❌ {error_msg}")
        logger.error(error_msg)
        return {'success': False, 'error': error_msg}


@shared_task(bind=True)
def analizar_sourcemeter(self, project_id: int):
    """
    Tarea específica para análisis solo con SourceMeter
    """
    try:
        from .models import Project

        project = Project.objects.get(id_project=project_id)
        print(f"\n🔍 Analizando con SourceMeter: {project.name}")

        project_key = sonar.normalizar_project_key(project.name)
        success, mensaje = source.analizar(project.path, project_key)

        if success:
            source.procesar(project, project_key)
            print(f"✅ SourceMeter completado para {project.name}")
            return {'success': True, 'message': mensaje}
        else:
            print(f"⚠️ SourceMeter: {mensaje}")
            return {'success': False, 'error': mensaje}

    except Exception as e:
        error_msg = f"Error en análisis SourceMeter: {str(e)}"
        print(f"❌ {error_msg}")
        logger.error(error_msg)
        return {'success': False, 'error': error_msg}
