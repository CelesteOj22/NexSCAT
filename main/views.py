import os
import time  # 🔥 AGREGADO
import pathlib
from datetime import datetime

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.db.models import Max
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from .models import Metric, Component, ProjectMeasure, ComponentMeasure, Class, ClassMeasure, Project, SonarToken
from main.services.factory import sonar, source
from .forms import SonarTokenForm

from .services.user import UserService

from .tasks import analizar_proyecto_completo, analizar_proyecto_paralelo, test_celery
from celery.result import AsyncResult

import json
from django.http import StreamingHttpResponse

import logging
logger = logging.getLogger(__name__)

# Imports de Django
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.core.exceptions import ValidationError


def homepage(request):
    return render(request=request, template_name="main/Index.html")


@login_required
def estado_herramientas(request):
    """
    Vista para verificar el estado de las herramientas de análisis
    """
    token = None
    try:
        token_obj = SonarToken.objects.get(user=request.user)
        token = token_obj.token if token_obj.token else None
    except SonarToken.DoesNotExist:
        pass

    sonar_status = {
        'nombre': 'SonarQube',
        'disponible': False,
        'mensaje': '',
        'requiere_token': True,
        'token_configurado': bool(token)
    }

    if token:
        try:
            sonar_status['disponible'] = sonar.is_up(token)
            if sonar_status['disponible']:
                sonar_status['mensaje'] = 'Servidor disponible y funcionando correctamente'
            else:
                sonar_status['mensaje'] = 'Servidor no disponible o con problemas'
        except Exception as e:
            sonar_status['mensaje'] = f'Error al verificar: {str(e)}'
    else:
        sonar_status['mensaje'] = 'Token no configurado. Configure su token para verificar el estado.'

    sourcemeter_status = {
        'nombre': 'SourceMeter',
        'disponible': False,
        'mensaje': '',
        'requiere_token': False
    }

    try:
        sourcemeter_status['disponible'] = source.is_up()
        if sourcemeter_status['disponible']:
            sourcemeter_status['mensaje'] = 'Herramienta disponible en el sistema'
        else:
            sourcemeter_status['mensaje'] = 'Herramienta no encontrada en el PATH del sistema'
    except Exception as e:
        sourcemeter_status['mensaje'] = f'Error al verificar: {str(e)}'

    context = {
        'sonar_status': sonar_status,
        'sourcemeter_status': sourcemeter_status,
    }

    return render(request, 'main/estado_herramientas.html', context)


def token_required(view_func):
    def wrapper(request, *args, **kwargs):
        try:
            token_obj = SonarToken.objects.get(user=request.user)
            if not token_obj.token:
                raise SonarToken.DoesNotExist
        except SonarToken.DoesNotExist:
            messages.error(request, "Necesitás configurar tu token de SonarQube antes de continuar.")
            return redirect('main:configurarToken')
        return view_func(request, *args, **kwargs)

    return wrapper


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('main:home')
        else:
            messages.error(request, 'Nombre de usuario o contraseña incorrectos.')

    return render(request, 'registration/login.html')


@login_required
@token_required
def importarProyecto(request):
    """
    Vista adaptativa con soporte para AJAX y SSE
    """
    if request.method == 'POST':
        path = request.POST.get('path')

        if not os.path.isdir(path):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': 'La ruta ingresada no es válida.'}, status=400)
            messages.error(request, 'La ruta ingresada no es válida.')
            return render(request, 'main/importarProyecto.html')

        usu_token = SonarToken.objects.get(user=request.user)

        try:
            sonar.check_tool_status(sonar, usu_token.token)
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': str(e)}, status=400)
            messages.error(request, str(e))
            return render(request, 'main/importarProyecto.html')

        directorio = pathlib.Path(path)
        proyectos = [p for p in directorio.iterdir() if p.is_dir()]

        celery_disponible = is_celery_available()

        if celery_disponible:
            logger.info("Celery disponible - Ejecutando analisis ASINCRONO")
            print("=" * 60)
            print("MODO: ASINCRONO CON CELERY")
            print("=" * 60)

            result = _analizar_asincrono(request, proyectos, usu_token)

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                task_ids = request.session.get('analysis_tasks', [])
                return JsonResponse({'task_ids': task_ids, 'mode': 'async'})

            return result
        else:
            logger.info("Celery no disponible - Ejecutando analisis SINCRONO con SSE")
            print("=" * 60)
            print("MODO: SINCRONO (SIN CELERY) - USANDO SSE")
            print("=" * 60)

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                request.session['analysis_path'] = path
                request.session['analysis_user_id'] = request.user.id
                request.session['analysis_token'] = usu_token.token
                request.session.save()

                return JsonResponse({'mode': 'sync', 'use_sse': True})

            result = _analizar_sincrono(request, proyectos, usu_token)
            return result

    return render(request, 'main/importarProyecto.html')


def _analizar_asincrono(request, proyectos, usu_token):
    """
    Análisis asíncrono usando Celery con paralelismo real
    """
    parallel_enabled = settings.ANALYSIS_CONFIG.ENABLE_PARALLEL
    mode_name = "PARALELO" if parallel_enabled else "ASÍNCRONO"

    print("=" * 70)
    print(f"🚀 MODO: {mode_name} CON CELERY")
    print("=" * 70)
    print(f"Proyectos a analizar: {len(proyectos)}")
    print(f"Paralelismo habilitado: {parallel_enabled}")
    print(f"Workers disponibles: {settings.ANALYSIS_CONFIG.CELERY_WORKERS}")

    if parallel_enabled:
        print("⚡ Cada proyecto se analizará con SonarQube y SourceMeter EN PARALELO")
    else:
        print("🔄 Análisis secuencial (SonarQube → SourceMeter)")

    print("=" * 70)

    task_ids = []
    total_projects = len(proyectos)

    for idx, proyecto in enumerate(proyectos, 1):
        try:
            print(f"\n[{idx}/{total_projects}] 🚀 Lanzando análisis para: {proyecto.name}")

            from .models import Project
            from main.services.factory import sonar

            project_key = sonar.normalizar_project_key(proyecto.name)

            project, created = Project.objects.update_or_create(
                key=project_key,
                defaults={
                    'name': proyecto.name,
                    'path': str(proyecto),
                    'created_by': request.user
                }
            )

            if created:
                print(f"  ✨ Proyecto creado: {project.name} (ID: {project.id_project})")
            else:
                print(f"  🔄 Proyecto existente: {project.name} (ID: {project.id_project})")

            if parallel_enabled:
                print(f"  ⚡ Modo: PARALELO (Sonar + Source simultáneos)")
                task = analizar_proyecto_paralelo.delay(
                    project_id=project.id_project,
                    token=usu_token.token
                )
            else:
                print(f"  🔄 Modo: SECUENCIAL (Sonar → Source)")
                task = analizar_proyecto_completo.delay(
                    proyecto_path=str(proyecto),
                    usuario_id=request.user.id,
                    token=usu_token.token
                )

            from django.utils import timezone
            task_info = {
                'project_id': project.id_project,
                'project_name': proyecto.name,
                'task_id': task.id,
                'mode': 'parallel' if parallel_enabled else 'sequential',
                'started_at': timezone.now().isoformat()
            }

            task_ids.append(task_info)

            print(f"  ✅ Tarea lanzada (Task ID: {task.id})")

        except Exception as e:
            print(f"  ❌ Error lanzando tarea para {proyecto.name}: {str(e)}")
            logger.error(f"Error lanzando análisis para {proyecto.name}: {str(e)}")
            messages.error(request, f"Error en {proyecto.name}: {str(e)}")

    if task_ids:
        request.session['analysis_tasks'] = task_ids
        request.session['analysis_mode'] = 'parallel' if parallel_enabled else 'sequential'

        # 🔥 AGREGADO: guardar tiempo de inicio y nombres para calcular duración del lote
        request.session['batch_started_at'] = time.time()
        request.session['batch_project_names'] = [p.name for p in proyectos]
        request.session['batch_time_saved'] = False

        request.session.modified = True

        mode_emoji = "⚡" if parallel_enabled else "🔄"
        mode_text = "en paralelo" if parallel_enabled else "secuencialmente"

        messages.success(
            request,
            f"{mode_emoji} {len(task_ids)} proyecto(s) enviado(s) para análisis "
            f"{mode_text} (Celery Workers: {settings.ANALYSIS_CONFIG.CELERY_WORKERS})"
        )

        print(f"\n{'=' * 70}")
        print(f"✅ RESUMEN:")
        print(f"  Proyectos enviados: {len(task_ids)}")
        print(f"  Modo de análisis: {mode_name}")
        print(f"  Workers Celery: {settings.ANALYSIS_CONFIG.CELERY_WORKERS}")
        print(f"{'=' * 70}\n")

        return redirect('main:monitorear_analisis')
    else:
        messages.error(request, "No se pudieron lanzar las tareas de análisis")
        return render(request, 'main/importarProyecto.html')


def _analizar_sincrono(request, proyectos, usu_token):
    """
    Análisis síncrono sin Celery
    """
    print(f"Comenzando el análisis de {len(proyectos)} proyecto/s de forma síncrona")

    tiempo_inicio = time.time()  # 🔥 AGREGADO
    nombres_proyectos = [p.name for p in proyectos]  # 🔥 AGREGADO

    proyectos_exitosos = 0
    proyectos_fallidos = 0
    errores = []

    for proyecto in proyectos:
        try:
            print(f"🔍 Analizando: {proyecto.name}")

            from .tasks import _analizar_proyecto_logica

            resultado = _analizar_proyecto_logica(
                proyecto_path=str(proyecto),
                usuario_id=request.user.id,
                token=usu_token.token
            )

            if resultado.get('success'):
                proyectos_exitosos += 1
                print(f"✅ {proyecto.name} completado")
            else:
                proyectos_fallidos += 1
                error_msg = resultado.get('error', 'Error desconocido')
                print(f"❌ {proyecto.name} falló: {error_msg}")
                errores.append(f"{proyecto.name}: {error_msg}")

        except Exception as e:
            proyectos_fallidos += 1
            print(f"❌ Error en {proyecto.name}: {str(e)}")
            errores.append(f"{proyecto.name}: {str(e)}")

    # 🔥 AGREGADO: guardar tiempo total del lote
    tiempo_total = time.time() - tiempo_inicio
    estado = "exitoso" if proyectos_fallidos == 0 else "con_errores"
    _guardar_tiempo_lote(nombres_proyectos, tiempo_total, estado)
    print(f"⏱️ Lote completado en {tiempo_total:.2f}s ({tiempo_total / 60:.2f} min) — Estado: {estado}")

    if proyectos_exitosos > 0:
        messages.success(
            request,
            f"✅ {proyectos_exitosos} proyecto(s) analizados correctamente (modo síncrono)"
        )

    if proyectos_fallidos > 0:
        messages.warning(
            request,
            f"⚠️ {proyectos_fallidos} proyecto(s) fallaron"
        )

        for error in errores[:3]:
            messages.error(request, error)

    return redirect('main:dashboardAnalisis')


@login_required
def monitorear_analisis(request):
    """
    Vista para monitorear el progreso de los análisis en Celery
    """
    task_data = request.session.get('analysis_tasks', [])

    if not task_data:
        messages.info(request, "No hay análisis en progreso")
        return redirect('main:dashboardAnalisis')

    context = {
        'tasks': task_data
    }

    return render(request, 'main/monitorear_analisis.html', context)


@login_required
def verificar_tarea(request, task_id):
    """
    API endpoint mejorado con información de paralelismo
    """
    task = AsyncResult(task_id)

    response = {
        'task_id': task_id,
        'state': task.state,
        'ready': task.ready(),
        'successful': task.successful() if task.ready() else None,
        'failed': task.failed() if task.ready() else None,
    }

    if task.state == 'PENDING':
        response['status'] = '⏳ Esperando en cola...'
        response['progress'] = 0
        response['current_step'] = 0
        response['total_steps'] = 5

    elif task.state == 'PROGRESS':
        info = task.info
        response['status'] = info.get('status', 'Procesando...')
        response['progress'] = info.get('percent', 0)
        response['current_step'] = info.get('current_step', 0)
        response['total_steps'] = info.get('total_steps', 5)
        response['mode'] = info.get('mode', 'sequential')

        if info.get('mode') == 'parallel':
            response['sonar_task_id'] = info.get('sonar_task_id')
            response['source_task_id'] = info.get('source_task_id')

    elif task.state == 'SUCCESS':
        result = task.result
        response['status'] = '✅ ¡Completado exitosamente!'
        response['progress'] = 100
        response['current_step'] = 5
        response['total_steps'] = 5
        response['result'] = result

        if isinstance(result, dict):
            response['mode'] = result.get('mode', 'sequential')

            if result.get('mode') == 'parallel':
                response['speedup'] = result.get('speedup', 1.0)
                response['time_saved'] = result.get('time_saved', 0)
                response['total_time'] = result.get('total_time', 0)

                speedup = result.get('speedup', 1.0)
                time_saved = result.get('time_saved', 0)

                if speedup > 1:
                    response['status'] = (
                        f"✅ ¡Completado! ⚡ {speedup:.2f}x más rápido "
                        f"(Ahorro: {time_saved:.1f}s)"
                    )

    elif task.state == 'FAILURE':
        response['status'] = '❌ Error en el análisis'
        response['progress'] = 0
        response['current_step'] = 0
        response['total_steps'] = 5
        response['error'] = str(task.info)

    else:
        response['status'] = task.state
        response['progress'] = 25
        response['current_step'] = 1
        response['total_steps'] = 5

    return JsonResponse(response)


@login_required
def verificar_tareas_batch(request):
    """
    API para verificar el estado de múltiples tareas
    POST con {"task_ids": ["id1", "id2", ...]}
    """
    if request.method == 'POST':
        data = json.loads(request.body)
        task_ids = data.get('task_ids', [])

        results = []
        all_done = True

        for task_id in task_ids:
            task = AsyncResult(task_id)
            ready = task.ready()
            if not ready:
                all_done = False
            results.append({
                'task_id': task_id,
                'state': task.state,
                'ready': ready,
                'successful': task.successful() if ready else None,
            })

        # 🔥 AGREGADO: guardar tiempo del lote cuando todas las tareas terminaron
        if all_done and not request.session.get('batch_time_saved'):
            started_at = request.session.get('batch_started_at')
            nombres = request.session.get('batch_project_names', [])

            if started_at:
                tiempo_total = time.time() - started_at
                all_successful = all(r.get('successful') for r in results)
                estado = "exitoso" if all_successful else "con_errores"

                _guardar_tiempo_lote(
                    proyectos=nombres,
                    tiempo_total=tiempo_total,
                    estado=estado
                )

                # Marcar como guardado para no duplicar si el cliente vuelve a consultar
                request.session['batch_time_saved'] = True
                request.session.modified = True

                print(f"⏱️ Lote (Celery) completado en {tiempo_total:.2f}s ({tiempo_total / 60:.2f} min) — Estado: {estado}")

        return JsonResponse({'tasks': results, 'all_done': all_done})

    return JsonResponse({'error': 'Método no permitido'}, status=405)


@login_required
@token_required
def analizar_proyecto_individual(request, project_id):
    """
    Analizar un proyecto individual de forma asíncrona
    """
    project = get_object_or_404(Project, id=project_id)
    usu_token = SonarToken.objects.get(user=request.user)

    try:
        task = analizar_proyecto_completo.delay(
            proyecto_path=project.path,
            usuario_id=request.user.id,
            token=usu_token.token
        )

        request.session[f'task_{project.id}'] = task.id

        messages.success(
            request,
            f"✅ Análisis iniciado para {project.name} (Task ID: {task.id})"
        )

        return redirect('main:ver_resultados', project_id=project.id)

    except Exception as e:
        messages.error(request, f"Error: {str(e)}")
        return redirect('main:dashboardAnalisis')


@login_required
def test_celery_view(request):
    """
    Vista simple para probar que Celery funciona
    """
    try:
        task = test_celery.delay()
        messages.success(
            request,
            f"✅ Tarea de prueba lanzada correctamente. Task ID: {task.id}"
        )
    except Exception as e:
        messages.error(request, f"❌ Error: {str(e)}")

    return redirect('main:home')


@login_required
def configurarToken(request):
    token_obj, _ = SonarToken.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = SonarTokenForm(request.POST, instance=token_obj)
        if form.is_valid():
            form.save()
            return redirect('main:home')
    else:
        form = SonarTokenForm(instance=token_obj)

    return render(request, "main/configurarToken.html", {"form": form})


@login_required
def dashboardAnalisis(request):
    """
    Vista del dashboard con estructura jerárquica
    """
    selected_level = request.GET.get('level', 'Proyecto')
    page_number = request.GET.get('page', 1)

    projects = Project.objects.all().order_by('name')
    metrics = Metric.objects.all().order_by('name')
    tools = Metric.objects.values_list('tool', flat=True).distinct()

    hierarchical_data = []

    for project in projects:
        project_node = {
            'type': 'project',
            'id': f'project_{project.id_project}',
            'project_id': project.id_project,
            'project_name': project.name,
            'project_key': project.key,
            'last_analysis': project.last_analysis_sq,
            'measures': [],
            'components': []
        }

        if selected_level in ['Proyecto', 'Todos']:
            project_measures = ProjectMeasure.objects.filter(
                id_project=project
            ).select_related('id_metric').order_by('id_metric__name')

            for pm in project_measures:
                project_node['measures'].append({
                    'level': 'Proyecto',
                    'metric_name': pm.id_metric.name,
                    'metric_key': pm.id_metric.key,
                    'tool': pm.id_metric.tool,
                    'value': pm.value,
                    'description': pm.id_metric.description or '',
                    'domain': pm.id_metric.domain,
                })

        if selected_level in ['Componente', 'Clase', 'Todos']:
            components = Component.objects.filter(
                id_project=project
            ).order_by('path')

            for component in components:
                component_display_name = component.path.split('/')[-1] if component.path else component.path
                component_node = {
                    'type': 'component',
                    'id': f'component_{component.id_component}',
                    'component_id': component.id_component,
                    'component_name': component.path,
                    'component_path': component.path,
                    'component_display_name': component_display_name,
                    'qualifier': component.qualifier,
                    'measures': [],
                    'classes': []
                }

                if selected_level in ['Componente', 'Todos']:
                    comp_measures = ComponentMeasure.objects.filter(
                        id_component=component
                    ).select_related('id_metric').order_by('id_metric__name')

                    for cm in comp_measures:
                        component_node['measures'].append({
                            'level': 'Componente',
                            'metric_name': cm.id_metric.name,
                            'metric_key': cm.id_metric.key,
                            'tool': cm.id_metric.tool,
                            'value': cm.value,
                            'description': cm.id_metric.description or '',
                            'domain': cm.id_metric.domain,
                        })

                if selected_level in ['Clase', 'Todos']:
                    classes = Class.objects.filter(
                        id_component=component
                    ).order_by('name')

                    for class_obj in classes:
                        class_node = {
                            'type': 'class',
                            'id': f'class_{class_obj.id_class}',
                            'class_id': class_obj.id_class,
                            'class_name': class_obj.name,
                            'measures': []
                        }

                        class_measures = ClassMeasure.objects.filter(
                            id_class=class_obj
                        ).select_related('id_metric').order_by('id_metric__name')

                        for clm in class_measures:
                            class_node['measures'].append({
                                'level': 'Clase',
                                'metric_name': clm.id_metric.name,
                                'metric_key': clm.id_metric.key,
                                'tool': clm.id_metric.tool,
                                'value': clm.value,
                                'description': clm.id_metric.description or '',
                                'domain': clm.id_metric.domain,
                            })

                        component_node['classes'].append(class_node)

                project_node['components'].append(component_node)

        hierarchical_data.append(project_node)

    total_projects = projects.count()
    total_project_measures = ProjectMeasure.objects.count()
    total_component_measures = ComponentMeasure.objects.count()
    total_class_measures = ClassMeasure.objects.count()

    if selected_level == 'Proyecto':
        total_measures = total_project_measures
    elif selected_level == 'Componente':
        total_measures = total_component_measures
    elif selected_level == 'Clase':
        total_measures = total_class_measures
    else:
        total_measures = total_project_measures + total_component_measures + total_class_measures

    total_tools = len(tools)

    last_analysis = Project.objects.filter(
        last_analysis_sq__isnull=False
    ).aggregate(Max('last_analysis_sq'))['last_analysis_sq__max']

    context = {
        'projects': projects,
        'metrics': metrics,
        'tools': tools,
        'hierarchical_data': hierarchical_data,
        'total_projects': total_projects,
        'total_measures': total_measures,
        'total_tools': total_tools,
        'total_project_measures': total_project_measures,
        'total_component_measures': total_component_measures,
        'total_class_measures': total_class_measures,
        'last_analysis': last_analysis,
        'selected_level': selected_level,
    }

    return render(request, 'main/dashboardAnalisisJerarquico.html', context)


@login_required
def ver_resultados(request, project_id):
    project = get_object_or_404(Project, id=project_id)

    project_measures = ProjectMeasure.objects.filter(
        id_project=project
    ).select_related('id_metric').order_by('id_metric__name')

    components = Component.objects.filter(
        id_project=project
    ).prefetch_related('componentmeasure_set__id_metric').order_by('path')

    components_with_measures = []
    for component in components:
        components_with_measures.append({
            'path': component.path,
            'qualifier': component.qualifier,
            'measures': component.componentmeasure_set.all()
        })

    classes = Component.objects.filter(
        id_project=project,
        qualifier='CLS'
    ).prefetch_related('componentmeasure_set__id_metric')

    classes_with_measures = []
    for class_obj in classes:
        classes_with_measures.append({
            'name': class_obj.path.split('/')[-1],
            'measures': class_obj.componentmeasure_set.all()
        })

    context = {
        'project': project,
        'project_measures': project_measures,
        'components': components_with_measures,
        'classes': classes_with_measures,
    }

    return render(request, 'main/resultados.html', context)


def is_celery_available():
    """
    Verifica si Celery/Redis está disponible y funcionando
    """
    try:
        from celery import current_app
        current_app.connection().ensure_connection(max_retries=1)
        return True
    except Exception as e:
        logger.info(f"Celery no disponible: {e}")
        return False


@login_required
def analizar_sse(request):
    """
    Vista para Server-Sent Events (streaming de progreso)
    """
    path = request.session.get('analysis_path')
    user_id = request.session.get('analysis_user_id')
    token = request.session.get('analysis_token')

    if not all([path, user_id, token]):
        def error_stream():
            yield f"data: {json.dumps({'type': 'error', 'message': 'Sesion invalida'})}\n\n"

        response = StreamingHttpResponse(error_stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response

    if not os.path.isdir(path):
        def error_stream():
            yield f"data: {json.dumps({'type': 'error', 'message': 'Ruta invalida'})}\n\n"

        response = StreamingHttpResponse(error_stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response

    directorio = pathlib.Path(path)
    proyectos = [p for p in directorio.iterdir() if p.is_dir()]
    nombres_proyectos = [p.name for p in proyectos]  # 🔥 AGREGADO

    def event_stream():
        """
        Generador que yielda eventos SSE durante el análisis
        """
        tiempo_inicio = time.time()  # 🔥 AGREGADO

        try:
            for proyecto in proyectos:
                for event_data in _analizar_proyecto_con_sse(str(proyecto), user_id, token):
                    yield f"data: {json.dumps(event_data)}\n\n"

            # 🔥 AGREGADO: guardar tiempo total del lote al completar
            tiempo_total = time.time() - tiempo_inicio
            _guardar_tiempo_lote(nombres_proyectos, tiempo_total, estado="exitoso")
            print(f"⏱️ Lote (SSE) completado en {tiempo_total:.2f}s ({tiempo_total / 60:.2f} min)")

            yield f"data: {json.dumps({'type': 'complete', 'redirect': '/dashboardAnalisis/'})}\n\n"

            if 'analysis_path' in request.session:
                del request.session['analysis_path']
            if 'analysis_user_id' in request.session:
                del request.session['analysis_user_id']
            if 'analysis_token' in request.session:
                del request.session['analysis_token']

        except Exception as e:
            # 🔥 AGREGADO: guardar tiempo incluso en caso de error
            tiempo_total = time.time() - tiempo_inicio
            _guardar_tiempo_lote(nombres_proyectos, tiempo_total, estado="fallido")

            logger.error(f"Error en SSE: {str(e)}")
            error_data = {'type': 'error', 'message': str(e)}
            yield f"data: {json.dumps(error_data)}\n\n"

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


def _analizar_proyecto_con_sse(proyecto_path: str, usuario_id: int, token: str):
    """
    Versión de análisis que yielda eventos para SSE
    """
    from .models import Project

    try:
        proyecto_path = pathlib.Path(proyecto_path)
        project_key = sonar.normalizar_project_key(proyecto_path.name)

        yield {'type': 'progress', 'step': 1, 'percent': 10, 'message': f'Inicializando {proyecto_path.name}...'}

        print(f"\n{'=' * 60}")
        print(f"ANALIZANDO: {proyecto_path.name}")
        print(f"Project Key: {project_key}")
        print(f"{'=' * 60}\n")

        user = User.objects.get(id=usuario_id)

        project, created = Project.objects.update_or_create(
            key=project_key,
            defaults={
                'name': proyecto_path.name,
                'path': str(proyecto_path),
                'created_by': user
            }
        )

        if created:
            print(f"Proyecto creado: {project.name} (ID: {project.id_project})")
        else:
            print(f"Proyecto existente: {project.name} (ID: {project.id_project})")

        yield {'type': 'progress', 'step': 1, 'percent': 20, 'message': 'Proyecto listo para análisis'}

        print("\n" + "=" * 60)
        print("FASE 1: Análisis con SonarQube")
        print("=" * 60)

        yield {'type': 'progress', 'step': 2, 'percent': 25, 'message': 'Ejecutando análisis de SonarQube...'}

        scanner_path = settings.SONAR_SCANNER_PATH
        success_sonar, mensaje_sonar = sonar.analizar(scanner_path, str(proyecto_path), token)

        if success_sonar:
            print("SonarQube: Análisis completado exitosamente")
            yield {'type': 'progress', 'step': 2, 'percent': 45, 'message': 'SonarQube completado, esperando procesamiento...'}
            print("Procesando métricas de SonarQube...")
            yield {'type': 'progress', 'step': 2, 'percent': 50, 'message': 'Procesando métricas de SonarQube...'}
            sonar.procesar_con_reintentos(project, token, project_key, max_reintentos=3)
            print("SonarQube: Métricas procesadas y guardadas")
            yield {'type': 'progress', 'step': 2, 'percent': 60, 'message': 'Métricas de SonarQube guardadas'}
        else:
            print(f"SonarQube falló: {mensaje_sonar}")
            yield {'type': 'error', 'message': f'SonarQube falló: {mensaje_sonar}'}
            return

        print("\n" + "=" * 60)
        print("FASE 2: Análisis con SourceMeter")
        print("=" * 60)

        yield {'type': 'progress', 'step': 3, 'percent': 65, 'message': 'Ejecutando análisis de SourceMeter...'}

        scanner_path = settings.SOURCEMETER_PATH
        success_source, mensaje_source = source.analizar(scanner_path, str(proyecto_path), proyecto_path.name)

        if success_source:
            print("SourceMeter: Análisis completado exitosamente")
            yield {'type': 'progress', 'step': 3, 'percent': 75, 'message': 'SourceMeter completado, procesando métricas...'}
            print("Procesando métricas de SourceMeter...")
            source.procesar(project, proyecto_path.name)
            print("SourceMeter: Métricas procesadas y guardadas")
            yield {'type': 'progress', 'step': 3, 'percent': 90, 'message': 'Métricas de SourceMeter guardadas'}
        else:
            print(f"SourceMeter: {mensaje_source}")
            yield {'type': 'progress', 'step': 3, 'percent': 85, 'message': f'Advertencia en SourceMeter: {mensaje_source}'}

        print(f"\n{'=' * 60}")
        print(f"ANÁLISIS COMPLETADO: {proyecto_path.name}")
        print(f"   SonarQube: {'OK' if success_sonar else 'Error'}")
        print(f"   SourceMeter: {'OK' if success_source else 'Warning'}")
        print(f"{'=' * 60}\n")

        yield {'type': 'progress', 'step': 5, 'percent': 100, 'message': 'Análisis completado exitosamente'}

    except Exception as e:
        print(f"\nERROR GENERAL: {str(e)}")
        import traceback
        traceback.print_exc()
        yield {'type': 'error', 'message': str(e)}


def is_superuser(user):
    return user.is_superuser


@login_required
@user_passes_test(lambda u: u.is_superuser)
def user_management(request):
    service = UserService()

    users_list = service.get_users_with_filters(
        search=request.GET.get('search'),
        status=request.GET.get('status'),
        role=request.GET.get('role')
    )

    paginator = Paginator(users_list, 15)
    page = request.GET.get('page')
    users = paginator.get_page(page)

    statistics = service.get_user_statistics()

    context = {
        'users': users,
        **statistics
    }

    return render(request, 'users/user_management.html', context)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def create_user(request):
    if request.method == 'POST':
        service = UserService()

        try:
            user = service.create_user(
                username=request.POST.get('username'),
                email=request.POST.get('email'),
                password1=request.POST.get('password1'),
                password2=request.POST.get('password2'),
                first_name=request.POST.get('first_name', ''),
                last_name=request.POST.get('last_name', ''),
                is_active=request.POST.get('is_active') == 'on',
                is_staff=request.POST.get('is_staff') == 'on',
                is_superuser=request.POST.get('is_superuser') == 'on'
            )

            messages.success(request, f'Usuario "{user.username}" creado exitosamente.')

        except ValidationError as e:
            messages.error(request, str(e))
        except Exception as e:
            logger.error(f'Error inesperado: {str(e)}')
            messages.error(request, 'Error inesperado al crear usuario.')

    return redirect('main:user_management')


@login_required
@user_passes_test(lambda u: u.is_superuser)
def get_user(request, user_id):
    service = UserService()

    try:
        user = service.get_user_by_id(user_id)
        data = service.get_user_data_dict(user)
        return JsonResponse(data)
    except ValidationError as e:
        return JsonResponse({'error': str(e)}, status=404)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def edit_user(request, user_id):
    if request.method == 'POST':
        service = UserService()

        try:
            user = service.update_user(
                user_id=user_id,
                username=request.POST.get('username'),
                email=request.POST.get('email'),
                first_name=request.POST.get('first_name', ''),
                last_name=request.POST.get('last_name', ''),
                password=request.POST.get('password') or None,
                is_active=request.POST.get('is_active') == 'on',
                is_staff=request.POST.get('is_staff') == 'on',
                is_superuser=request.POST.get('is_superuser') == 'on'
            )

            messages.success(request, f'Usuario "{user.username}" actualizado exitosamente.')

        except ValidationError as e:
            messages.error(request, str(e))
        except Exception as e:
            logger.error(f'Error inesperado: {str(e)}')
            messages.error(request, 'Error inesperado al actualizar usuario.')

    return redirect('main:user_management')


@login_required
@user_passes_test(lambda u: u.is_superuser)
def delete_user(request, user_id):
    if request.method == 'POST':
        service = UserService()

        try:
            username = service.delete_user(user_id, request.user.id)
            messages.success(request, f'Usuario "{username}" eliminado exitosamente.')

        except ValidationError as e:
            messages.error(request, str(e))
        except Exception as e:
            logger.error(f'Error inesperado: {str(e)}')
            messages.error(request, 'Error inesperado al eliminar usuario.')

    return redirect('main:user_management')


@login_required
def obtener_datos_jerarquicos(request):
    """
    Endpoint que devuelve los datos en formato jerárquico
    """
    selected_level = request.GET.get('level', 'Todos')

    projects = Project.objects.all()
    data = []

    for project in projects:
        project_data = {
            'project': {
                'id': project.id_project,
                'key': project.key or '',
                'name': project.name,
                'lastAnalysis': project.last_analysis_sq.isoformat() if project.last_analysis_sq else None
            },
            'project_measures': []
        }

        if selected_level in ['Proyecto', 'Todos']:
            project_measures = ProjectMeasure.objects.filter(
                id_project=project
            ).select_related('id_metric')

            for pm in project_measures:
                project_data['project_measures'].append({
                    'domain': pm.id_metric.domain if hasattr(pm.id_metric, 'domain') else '',
                    'key': pm.id_metric.key,
                    'name': pm.id_metric.name,
                    'description': pm.id_metric.description if hasattr(pm.id_metric, 'description') else '',
                    'type': pm.id_metric.type if hasattr(pm.id_metric, 'type') else '',
                    'value': str(pm.value or ''),
                    'tool': pm.id_metric.tool
                })

        project_data['components'] = []

        if selected_level in ['Componente', 'Clase', 'Todos']:
            components = Component.objects.filter(id_project=project).order_by('path')

            for component in components:
                component_data = {
                    'component': {
                        'id': component.id_component,
                        'name': component.path,
                        'qualifier': component.qualifier,
                        'path': component.path,
                        'language': ''
                    },
                    'component_measures': []
                }

                if selected_level in ['Componente', 'Todos']:
                    comp_measures = ComponentMeasure.objects.filter(
                        id_component=component
                    ).select_related('id_metric')

                    for cm in comp_measures:
                        component_data['component_measures'].append({
                            'domain': cm.id_metric.domain if hasattr(cm.id_metric, 'domain') else '',
                            'key': cm.id_metric.key,
                            'name': cm.id_metric.name,
                            'description': cm.id_metric.description if hasattr(cm.id_metric, 'description') else '',
                            'type': cm.id_metric.type if hasattr(cm.id_metric, 'type') else '',
                            'value': str(cm.value or ''),
                            'tool': cm.id_metric.tool
                        })

                component_data['classes'] = []

                if selected_level in ['Clase', 'Todos']:
                    try:
                        from .models import Class, ClassMeasure

                        classes = Class.objects.filter(id_component=component)

                        for class_obj in classes:
                            class_data = {
                                'class': {
                                    'id': class_obj.id_class,
                                    'name': class_obj.name,
                                    'qualifier': ''
                                },
                                'class_measures': []
                            }

                            class_measures = ClassMeasure.objects.filter(
                                id_class=class_obj
                            ).select_related('id_metric')

                            for clm in class_measures:
                                class_data['class_measures'].append({
                                    'domain': clm.id_metric.domain if hasattr(clm.id_metric, 'domain') else '',
                                    'key': clm.id_metric.key,
                                    'name': clm.id_metric.name,
                                    'description': clm.id_metric.description if hasattr(clm.id_metric, 'description') else '',
                                    'type': clm.id_metric.type if hasattr(clm.id_metric, 'type') else '',
                                    'value': str(clm.value or ''),
                                    'tool': clm.id_metric.tool
                                })

                            component_data['classes'].append(class_data)
                    except ImportError:
                        pass

                project_data['components'].append(component_data)

        data.append(project_data)

    return JsonResponse({'data': data}, safe=False)


@login_required
def estadisticas_paralelo(request):
    """
    Vista para mostrar estadísticas de análisis paralelo vs secuencial
    """
    tasks = request.session.get('analysis_tasks', [])
    mode = request.session.get('analysis_mode', 'sequential')

    stats = {
        'total_projects': len(tasks),
        'mode': mode,
        'workers': settings.ANALYSIS_CONFIG.CELERY_WORKERS,
        'parallel_enabled': settings.ANALYSIS_CONFIG.ENABLE_PARALLEL,
        'completed': 0,
        'pending': 0,
        'failed': 0,
        'total_speedup': 0,
        'total_time_saved': 0,
    }

    for task_info in tasks:
        task = AsyncResult(task_info['task_id'])

        if task.successful():
            stats['completed'] += 1
            result = task.result

            if isinstance(result, dict) and result.get('mode') == 'parallel':
                stats['total_speedup'] += result.get('speedup', 1.0)
                stats['total_time_saved'] += result.get('time_saved', 0)

        elif task.failed():
            stats['failed'] += 1
        else:
            stats['pending'] += 1

    if stats['completed'] > 0:
        stats['avg_speedup'] = stats['total_speedup'] / stats['completed']
    else:
        stats['avg_speedup'] = 0

    context = {
        'stats': stats,
        'tasks': tasks,
    }

    return render(request, 'main/estadisticas_paralelo.html', context)


def _guardar_tiempo_lote(proyectos: list, tiempo_total: float, estado: str = "exitoso"):
    """Guarda el tiempo total del lote en un archivo JSON."""

    log_dir = pathlib.Path(settings.BASE_DIR) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "batch_times.json"

    if log_file.exists():
        with open(log_file, "r") as f:
            registros = json.load(f)
    else:
        registros = []

    registros.append({
        "fecha": datetime.now().isoformat(),
        "cantidad_proyectos": len(proyectos),
        "proyectos": proyectos,
        "tiempo_segundos": round(tiempo_total, 2),
        "tiempo_minutos": round(tiempo_total / 60, 2),
        "estado": estado
    })

    with open(log_file, "w") as f:
        json.dump(registros, f, indent=2, ensure_ascii=False)