import os
import pathlib

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib import messages
# para renderizar templates?
from django.utils import timezone

from .models import Metric, Project, SonarToken
from main.services.factory import sonar, source
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
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
        """
        try:
            sonar.check_tool_status(sonar, usu_token.token)
        except Exception as e:
            messages.error(request, str(e))
            return render(request, 'main/importarProyecto.html')
        """

        directorio = pathlib.Path(path)
        print("Comenzando el analisis de " + str(len(os.listdir(path))) + " proyecto/s")

        resultados = {}
        errores = {}

        for proyecto in directorio.iterdir():
            try:
                resultado = analizarProyectos(str(proyecto), request.user)
                resultados[proyecto.name] = resultado
            except Exception as e:
                errores[proyecto.name] = str(e)

        return render(request, 'main/resultado.html', {
            'mensaje': f'Análisis de {path} completado.',
            'resultados': resultados,
            'errores': errores
        })

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
        """
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
                # 🆕 USAR EL MÉTODO CON REINTENTOS
                try:
                    sonar.procesar_con_reintentos(project, usu_token.token, project_key)
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

        return resultados

    except Exception as e:
        print(f"❌ Error general en analizarProyectos({proyecto_path}): {e}")
        raise

"""
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
                # Solo procesar métricas si el análisis fue exitoso
                sonar.procesar(project, usu_token.token, project_key)
                update_project(project_name, timezone.now(), "sq")
            else:
                print(f"❌ No se procesan métricas para {project_name} porque el análisis falló")
                print("❌ Análisis falló, salida completa del scanner:")
                print(mensaje)

        except Exception as e:
            print(f"❌ Error en SonarQube para {project_name}: {e}")
            resultados["sonar_error"] = str(e)

        
        # 🔹 Analizar con SourceMeter (opcional, pausado)
        try:
            resultado_source = source.analizar(settings.SOURCEMETER_PATH, proyecto_path)
            # source.procesar(project, resultado_source) --pausado hasta nuevo aviso
            resultados["sourcemeter"] = resultado_source
            update_project(project_name, timezone.now(), "sm")
        except Exception as e:
            print(f"❌ Error en SourceMeter para {project_name}: {e}")
            resultados["sourcemeter_error"] = str(e)
        

        return resultados

    except Exception as e:
        print(f"❌ Error general en analizarProyectos({proyecto_path}): {e}")
        raise  # para que lo capture importarProyecto
"""

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

