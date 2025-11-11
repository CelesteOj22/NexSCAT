import os
import pathlib

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib import messages
# para renderizar templates?
from django.db.models import Max
from django.utils import timezone

from .models import Metric, Project, SonarToken, Component, ProjectMeasure
from main.services.factory import sonar, source
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from .forms import SonarTokenForm
from .models import SonarToken

# Create your views here.
from .repository.projectRepository import update_project
from .services.base import IHerramienta


def homepage(request):
    # print(Projects.objects.all().query)
    # print(Projects.objects.all())
    # metrics_query = Metrics.objects.all().query
    # print(metrics_query)
    # metrics1 = Metrics.objects.all()
    # print(metrics1)  # Verifica los resultados en la consola
    # parametros de render(request,template,content/data)
    return render(request=request, template_name="main/Index.html", context={"metrics": Metric.objects.all})


"""
def login(request):
    return render(request=request, template_name="registration/login.html")
"""


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


# mi decorador va arriba de la definicion de la vista wuau
@login_required
@token_required
def importarProyecto(request):
    if request.method == 'POST':
        path = request.POST.get('path')
        if not os.path.isdir(path):
            messages.error(request, 'La ruta ingresada no es válida.')
            return render(request, 'main/importarProyecto.html')

        usu_token = SonarToken.objects.get(user=request.user)

        try:
            sonar.check_tool_status(sonar, usu_token.token)
        except Exception as e:
            messages.error(request, str(e))
            return render(request, 'main/importarProyecto.html')

        directorio = pathlib.Path(path)
        print(f"Comenzando el análisis de {len(list(directorio.iterdir()))} proyecto/s")

        proyectos_exitosos = 0
        proyectos_fallidos = 0

        for proyecto in directorio.iterdir():
            if not proyecto.is_dir():
                continue

            try:
                print(f"\n{'=' * 60}")
                print(f"🚀 Analizando: {proyecto.name}")
                print(f"{'=' * 60}")

                analizarProyectos(str(proyecto), request.user)
                proyectos_exitosos += 1

                print(f"✅ {proyecto.name} completado")

            except Exception as e:
                print(f"❌ Error en {proyecto.name}: {str(e)}")
                proyectos_fallidos += 1

        # Mostrar mensaje de resumen
        if proyectos_exitosos > 0:
            messages.success(
                request,
                f"✅ Análisis completado: {proyectos_exitosos} proyectos exitosos"
            )

        if proyectos_fallidos > 0:
            messages.warning(
                request,
                f"⚠️ {proyectos_fallidos} proyectos con errores"
            )

        # Redirigir al dashboard
        from django.shortcuts import redirect
        return redirect('main:dashboardAnalisis')

    return render(request, 'main/importarProyecto.html')

def analizarProyectos(proyecto_path, usu_logueado):
    try:
        project_name = pathlib.Path(proyecto_path).name
        usu_token = SonarToken.objects.get(user=usu_logueado)

        # 🔹 Normalizar projectKey con prefijo nexscat:
        project_key = sonar.normalizar_project_key(project_name)

        # 🔹 Crear o recuperar el proyecto en la base de datos
        project, created = Project.objects.get_or_create(
            name=project_name,
            defaults={
                "path": proyecto_path,
                "created_by": usu_logueado,
                "created_at": timezone.now(),
                "key": project_key
            }
        )

        if not created:
            print(f"📌 Proyecto {project_name} ya existía en la base")
        else:
            print(f"✅ Proyecto {project_name} creado en la base con key {project_key}")

        resultados = {}

        # 🔹 Analizar con SonarQube
        try:
            # Analizar el proyecto
            resultado_ok, mensaje = sonar.analizar(
                settings.SONAR_SCANNER_PATH,
                proyecto_path,
                usu_token.token
            )
            resultados["sonar"] = mensaje

            if resultado_ok:
                try:
                    # Procesar métricas a nivel PROYECTO (tu código actual)
                    sonar.procesar_con_reintentos(project, usu_token.token, project_key)

                    # Procesar componentes (archivos y directorios)
                    sonar.procesar_componentes(project, usu_token.token, project_key)

                    update_project(project_name, timezone.now(), "sq")
                    resultados["sonar_metrics"] = "✅ Métricas procesadas exitosamente"
                except Exception as e:
                    print(f"❌ Error procesando métricas para {project_name}: {e}")
                    resultados["sonar_metrics_error"] = f"Error: {str(e)}"
            else:
                print(f"❌ No se procesan métricas para {project_name} porque el análisis falló")
                print("❌ Análisis falló, salida completa del scanner:")
                print(mensaje)

        except Exception as e:
            print(f"❌ Error en SonarQube para {project_name}: {e}")
            resultados["sonar_error"] = str(e)
        """
        # 🔹 Analizar con SourceMeter
        try:
            resultado_ok, mensaje = source.analizar(
                settings.SOURCEMETER_PATH,
                proyecto_path,
                project_name  # ← SIN normalizar (checkstyle-4.3)
            )
            resultados["sourcemeter"] = mensaje
            if resultado_ok:
                # ✅ PROCESAR DESPUÉS DE ANALIZAR
                try:
                    source.procesar(project, project_name)  # ← Pasar project_name, no project_key
                    update_project(project_name, timezone.now(), "sm")
                    resultados["sourcemeter_metrics"] = "✅ Métricas procesadas exitosamente"
                except Exception as e:
                    print(f"❌ Error procesando métricas para {project_name}: {e}")
                    resultados["sourcemeter_metrics_error"] = f"Error: {str(e)}"
            else:
                print(f"❌ No se procesan métricas para {project_name} porque el análisis falló")

        except Exception as e:
            print(f"❌ Error en SourceMeter para {project_name}: {e}")
            resultados["sourcemeter_error"] = str(e)
        """
        return project

    except Exception as e:
        print(f"❌ Error general en analizarProyectos({proyecto_path}): {e}")
        raise

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

