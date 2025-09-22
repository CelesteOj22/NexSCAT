# tasks.py
from celery import shared_task
from main.models import Project
from main.analysis import sonar, source, update_project
from django.utils import timezone
import pathlib, settings

@shared_task
def analizar_sonar(proyecto_path, usuario_id):
    project_name = pathlib.Path(proyecto_path).name
    project, _ = Project.objects.get_or_create(
        name=project_name,
        defaults={"path": proyecto_path, "created_by_id": usuario_id, "created_at": timezone.now()}
    )

    resultados = {}
    try:
        resultado_sonar = sonar.analizar(settings.SONAR_SCANNER_PATH, proyecto_path)
        resultados["sonar"] = resultado_sonar
        update_project(project_name, timezone.now(), "sq")
    except Exception as e:
        resultados["sonar_error"] = str(e)
    return resultados

@shared_task
def analizar_sourcemeter(proyecto_path, usuario_id):
    project_name = pathlib.Path(proyecto_path).name
    project, _ = Project.objects.get_or_create(
        name=project_name,
        defaults={"path": proyecto_path, "created_by_id": usuario_id, "created_at": timezone.now()}
    )

    resultados = {}
    try:
        resultado_source = source.analizar(settings.SOURCEMETER_PATH, proyecto_path)
        resultados["sourcemeter"] = resultado_source
        update_project(project_name, timezone.now(), "sm")
    except Exception as e:
        resultados["sourcemeter_error"] = str(e)
    return resultados
