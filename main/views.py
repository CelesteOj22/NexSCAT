import os
import pathlib

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib import messages
# para renderizar templates?
from django.contrib.auth.models import User
from django.db.models import Max
from django.http import JsonResponse
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from .models import Metric, Project, SonarToken, Component, ProjectMeasure
from main.services.factory import sonar, source
from .forms import SonarTokenForm
from .repository.projectRepository import update_project

from .tasks import analizar_proyecto_completo, analizar_sonar, analizar_sourcemeter, test_celery
from celery.result import AsyncResult

import json
from django.http import StreamingHttpResponse

import logging
logger = logging.getLogger(__name__)


def homepage(request):
    # print(Projects.objects.all().query)
    # print(Projects.objects.all())
    # metrics_query = Metrics.objects.all().query
    # print(metrics_query)
    # metrics1 = Metrics.objects.all()
    # print(metrics1)  # Verifica los resultados en la consola
    # parametros de render(request,template,content/data)
    return render(request=request, template_name="main/Index.html", context={"metrics": Metric.objects.all})

@login_required
def estado_herramientas(request):
    """
    Vista para verificar el estado de las herramientas de análisis
    """
    # Obtener token del usuario
    token_obj = None
    token = None
    try:
        token_obj = SonarToken.objects.get(user=request.user)
        token = token_obj.token if token_obj.token else None
    except SonarToken.DoesNotExist:
        pass

    # Verificar estado de SonarQube
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

    # Verificar estado de SourceMeter
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
            return redirect('main:home')  # nombre de la URL definida para el home
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

            # Guardar en sesión para SSE
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
    Análisis asíncrono usando Celery
    """
    print(f"Comenzando el análisis de {len(proyectos)} proyecto/s usando Celery")

    task_ids = []

    for proyecto in proyectos:
        try:
            print(f"🚀 Lanzando análisis asíncrono para: {proyecto.name}")

            # Lanzar tarea de Celery
            task = analizar_proyecto_completo.delay(
                proyecto_path=str(proyecto),
                usuario_id=request.user.id,
                token=usu_token.token
            )

            task_ids.append({
                'project_name': proyecto.name,
                'task_id': task.id
            })

            print(f"✅ Tarea lanzada para {proyecto.name} (Task ID: {task.id})")

        except Exception as e:
            print(f"❌ Error lanzando tarea para {proyecto.name}: {str(e)}")
            messages.error(request, f"Error en {proyecto.name}: {str(e)}")

    if task_ids:
        request.session['analysis_tasks'] = task_ids
        messages.success(
            request,
            f"✅ {len(task_ids)} proyectos enviados para análisis en segundo plano (Celery)"
        )
        return redirect('main:monitorear_analisis')
    else:
        messages.error(request, "No se pudieron lanzar las tareas de análisis")
        return render(request, 'main/importarProyecto.html')


def _analizar_sincrono(request, proyectos, usu_token):
    """
    Análisis síncrono sin Celery
    """
    print(f"Comenzando el análisis de {len(proyectos)} proyecto/s de forma síncrona")

    proyectos_exitosos = 0
    proyectos_fallidos = 0
    errores = []

    for proyecto in proyectos:
        try:
            print(f"🔍 Analizando: {proyecto.name}")

            # Importar la función de la tarea (sin .delay())
            from .tasks import _analizar_proyecto_logica

            # Llamar directamente a la lógica (sin Celery)
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

    # Mostrar resultados
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

        # Mostrar detalles de errores
        for error in errores[:3]:  # Mostrar máximo 3 errores
            messages.error(request, error)

    return redirect('main:dashboardAnalisis')

# 🔥 NUEVA VISTA: Monitorear progreso de análisis
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
    API endpoint mejorado para verificar el estado con progreso detallado
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
        response['status'] = 'Esperando en cola...'
        response['progress'] = 0
        response['current_step'] = 0
        response['total_steps'] = 5

    elif task.state == 'PROGRESS':
        # 🔥 Estado personalizado con info detallada
        info = task.info
        response['status'] = info.get('status', 'Procesando...')
        response['progress'] = info.get('percent', 0)
        response['current_step'] = info.get('current_step', 0)
        response['total_steps'] = info.get('total_steps', 5)

    elif task.state == 'SUCCESS':
        response['status'] = '¡Completado exitosamente! ✅'
        response['progress'] = 100
        response['current_step'] = 5
        response['total_steps'] = 5
        response['result'] = task.result

    elif task.state == 'FAILURE':
        response['status'] = 'Error en el análisis ❌'
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
    import json

    if request.method == 'POST':
        data = json.loads(request.body)
        task_ids = data.get('task_ids', [])

        results = []
        for task_id in task_ids:
            task = AsyncResult(task_id)
            results.append({
                'task_id': task_id,
                'state': task.state,
                'ready': task.ready(),
                'successful': task.successful() if task.ready() else None,
            })

        return JsonResponse({'tasks': results})

    return JsonResponse({'error': 'Método no permitido'}, status=405)


# 🔥 VISTA OPCIONAL: Análisis individual con Celery
@login_required
@token_required
def analizar_proyecto_individual(request, project_id):
    """
    Analizar un proyecto individual de forma asíncrona
    """
    project = get_object_or_404(Project, id=project_id)
    usu_token = SonarToken.objects.get(user=request.user)

    try:
        # Lanzar análisis asíncrono
        task = analizar_proyecto_completo.delay(
            proyecto_path=project.path,
            usuario_id=request.user.id,
            token=usu_token.token
        )

        # Guardar task_id en la sesión
        request.session[f'task_{project.id}'] = task.id

        messages.success(
            request,
            f"✅ Análisis iniciado para {project.name} (Task ID: {task.id})"
        )

        return redirect('main:ver_resultados', project_id=project.id)

    except Exception as e:
        messages.error(request, f"Error: {str(e)}")
        return redirect('main:dashboardAnalisis')


# 🔥 VISTA DE PRUEBA: Probar Celery
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
            return redirect('main:home')  # Cambiar por la url que quieras
    else:
        form = SonarTokenForm(instance=token_obj)

    return render(request, "main/configurarToken.html", {"form": form})


@login_required
def dashboardAnalisis(request):
    """
    Vista general del dashboard con todas las métricas de todos los proyectos
    """
    # Obtener todos los proyectos del usuario (o todos si es admin)
    projects = Project.objects.all().order_by('name')

    # Obtener todas las métricas disponibles
    metrics = Metric.objects.all().order_by('name')

    # Obtener todas las herramientas únicas
    tools = Metric.objects.values_list('tool', flat=True).distinct()

    # Obtener todas las medidas de proyectos
    project_measures = ProjectMeasure.objects.select_related(
        'id_project', 'id_metric'
    ).all()

    # Preparar datos para la tabla
    measures_data = []
    for measure in project_measures:
        measures_data.append({
            'project_name': measure.id_project.name,
            'project_key': measure.id_project.key,
            'metric_name': measure.id_metric.name,
            'metric_key': measure.id_metric.key,
            'tool': measure.id_metric.tool,
            'value': measure.value,
            'description': measure.id_metric.description or '',
        })

    # Calcular estadísticas
    total_projects = projects.count()
    total_measures = project_measures.count()
    total_tools = len(tools)

    # Último análisis
    last_analysis = Project.objects.filter(
        last_analysis_sq__isnull=False
    ).aggregate(Max('last_analysis_sq'))['last_analysis_sq__max']

    context = {
        'projects': projects,
        'metrics': metrics,
        'tools': tools,
        'measures': measures_data,
        'total_projects': total_projects,
        'total_measures': total_measures,
        'total_tools': total_tools,
        'last_analysis': last_analysis,
    }

    return render(request, 'main/dashboardAnalisis.html', context)


@login_required
def ver_resultados(request, project_id):
    """
    Vista para mostrar los resultados detallados del análisis de un proyecto
    """
    project = get_object_or_404(Project, id=project_id)

    # Verificar que el usuario tenga permiso (opcional)
    # if project.user != request.user:
    #     return HttpResponseForbidden()

    # Métricas del proyecto
    project_measures = ProjectMeasure.objects.filter(
        id_project=project
    ).select_related('id_metric').order_by('id_metric__name')

    # Componentes con sus métricas
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

    # Clases (si aplica)
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
        # Intentar hacer ping al broker
        current_app.connection().ensure_connection(max_retries=1)
        return True
    except Exception as e:
        logger.info(f"Celery no disponible: {e}")
        return False


@login_required
def analizar_sse(request):
    """
    Vista para Server-Sent Events (streaming de progreso)
    IMPORTANTE: EventSource siempre usa GET
    """
    # Obtener datos de la sesión
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

    def event_stream():
        """
        Generador que yielda eventos SSE durante el análisis
        """
        try:
            for proyecto in proyectos:
                # Llamar a la lógica con callback para SSE
                for event_data in _analizar_proyecto_con_sse(
                        str(proyecto),
                        user_id,
                        token
                ):
                    # Formatear como Server-Sent Event
                    yield f"data: {json.dumps(event_data)}\n\n"

            # Evento final de completado
            yield f"data: {json.dumps({'type': 'complete', 'redirect': '/dashboardAnalisis/'})}\n\n"

            # Limpiar sesión
            if 'analysis_path' in request.session:
                del request.session['analysis_path']
            if 'analysis_user_id' in request.session:
                del request.session['analysis_user_id']
            if 'analysis_token' in request.session:
                del request.session['analysis_token']

        except Exception as e:
            logger.error(f"Error en SSE: {str(e)}")
            error_data = {
                'type': 'error',
                'message': str(e)
            }
            yield f"data: {json.dumps(error_data)}\n\n"

    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
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

        # Evento 1: Inicialización
        yield {
            'type': 'progress',
            'step': 1,
            'percent': 10,
            'message': f'Inicializando {proyecto_path.name}...'
        }

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

        yield {
            'type': 'progress',
            'step': 1,
            'percent': 20,
            'message': 'Proyecto listo para análisis'
        }

        # Evento 2: SonarQube
        print("\n" + "=" * 60)
        print("FASE 1: Análisis con SonarQube")
        print("=" * 60)

        yield {
            'type': 'progress',
            'step': 2,
            'percent': 25,
            'message': 'Ejecutando análisis de SonarQube...'
        }

        scanner_path = settings.SONAR_SCANNER_PATH
        success_sonar, mensaje_sonar = sonar.analizar(
            scanner_path,
            str(proyecto_path),
            token
        )

        if success_sonar:
            print("SonarQube: Análisis completado exitosamente")

            yield {
                'type': 'progress',
                'step': 2,
                'percent': 45,
                'message': 'SonarQube completado, esperando procesamiento...'
            }

            print("Procesando métricas de SonarQube...")

            yield {
                'type': 'progress',
                'step': 2,
                'percent': 50,
                'message': 'Procesando métricas de SonarQube...'
            }

            sonar.procesar_con_reintentos(project, token, project_key, max_reintentos=3)

            print("SonarQube: Métricas procesadas y guardadas")

            yield {
                'type': 'progress',
                'step': 2,
                'percent': 60,
                'message': 'Métricas de SonarQube guardadas'
            }
        else:
            print(f"SonarQube falló: {mensaje_sonar}")
            yield {
                'type': 'error',
                'message': f'SonarQube falló: {mensaje_sonar}'
            }
            return

        # Evento 3: SourceMeter
        print("\n" + "=" * 60)
        print("FASE 2: Análisis con SourceMeter")
        print("=" * 60)

        yield {
            'type': 'progress',
            'step': 3,
            'percent': 65,
            'message': 'Ejecutando análisis de SourceMeter...'
        }

        scanner_path = settings.SOURCEMETER_PATH
        success_source, mensaje_source = source.analizar(
            scanner_path,
            str(proyecto_path),
            proyecto_path.name
        )

        if success_source:
            print("SourceMeter: Análisis completado exitosamente")

            yield {
                'type': 'progress',
                'step': 3,
                'percent': 75,
                'message': 'SourceMeter completado, procesando métricas...'
            }

            print("Procesando métricas de SourceMeter...")

            source.procesar(project, project_key)

            print("SourceMeter: Métricas procesadas y guardadas")

            yield {
                'type': 'progress',
                'step': 3,
                'percent': 90,
                'message': 'Métricas de SourceMeter guardadas'
            }
        else:
            print(f"SourceMeter: {mensaje_source}")
            yield {
                'type': 'progress',
                'step': 3,
                'percent': 85,
                'message': f'Advertencia en SourceMeter: {mensaje_source}'
            }

        # Evento 4: Finalización
        print(f"\n{'=' * 60}")
        print(f"ANÁLISIS COMPLETADO: {proyecto_path.name}")
        print(f"   SonarQube: {'OK' if success_sonar else 'Error'}")
        print(f"   SourceMeter: {'OK' if success_source else 'Warning'}")
        print(f"{'=' * 60}\n")

        yield {
            'type': 'progress',
            'step': 5,
            'percent': 100,
            'message': 'Análisis completado exitosamente'
        }

    except Exception as e:
        print(f"\nERROR GENERAL: {str(e)}")
        import traceback
        traceback.print_exc()

        yield {
            'type': 'error',
            'message': str(e)
        }