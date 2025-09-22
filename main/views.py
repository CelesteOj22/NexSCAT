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


def homepage(request):
    #print(Projects.objects.all().query)
    #print(Projects.objects.all())
    #metrics_query = Metrics.objects.all().query
    #print(metrics_query)
    #metrics1 = Metrics.objects.all()
    #print(metrics1)  # Verifica los resultados en la consola
    #parametros de render(request,template,content/data)
    return render(request=request, template_name="main/Index.html", context={"metrics": Metric.objects.all})

"""
def login(request):
    return render(request=request, template_name="registration/login.html")
"""
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

#mi decorador va arriba de la definicion de la vista wuau
@login_required()
def importarProyecto(request):
    if request.method == 'POST':
        path = request.POST.get('path')

        if not os.path.isdir(path):
            return render(request, 'main/importarProyecto.html', {'error': 'La ruta ingresada no es válida.'})

        directorio = pathlib.Path(path)
        print("Comenzando el analisis de " + str(len(os.listdir(path))) + " proyecto/s")

        resultados = {}
        errores = {}

        for proyecto in directorio.iterdir():
            try:
                resultado = analizarProyectos(str(proyecto), request.user)
                resultados[proyecto.name] = resultado
            except Exception as e:
                print(f"❌ Error analizando {proyecto.name}: {e}")
                errores[proyecto.name] = str(e)

        return render(request, 'main/resultado.html', {
            'mensaje': f'Análisis de {path} completado.',
            'resultados': resultados,
            'errores': errores
        })

    return render(request, 'main/importarProyecto.html')


def analizarProyectos(proyecto, usu_logueado):
    try:
        project_name = pathlib.Path(proyecto).name

        project, created = Project.objects.get_or_create(
            name=project_name,
            defaults={"path": proyecto, "created_by": usu_logueado, "created_at": timezone.now()}
        )

        if not created:
            print(f"📌 Proyecto {project_name} ya existía en la base")
        else:
            print(f"✅ Proyecto {project_name} creado en la base")

        resultados = {}

        # 🔹 Analizar y procesar con SonarQube
        try:
            resultado_sonar = sonar.analizar(settings.SONAR_SCANNER_PATH, proyecto)
            sonar.procesar(project, resultado_sonar)
            resultados["sonar"] = resultado_sonar
            update_project(project_name, timezone.now(), "sq")
        except Exception as e:
            print(f"❌ Error en SonarQube para {project_name}: {e}")
            resultados["sonar_error"] = str(e)
        """
        # 🔹 Analizar y procesar con SourceMeter
        try:
            resultado_source = source.analizar(settings.SOURCEMETER_PATH, proyecto)
            #source.procesar(project, resultado_source) --pausado hasta nuevo aviso
            resultados["sourcemeter"] = resultado_source
            update_project(project_name, timezone.now(), "sm")
        except Exception as e:
            print(f"❌ Error en SourceMeter para {project_name}: {e}")
            resultados["sourcemeter_error"] = str(e)
        """
        return resultados

    except Exception as e:
        print(f"❌ Error general en analizarProyectos({proyecto}): {e}")
        raise  # lo dejo subir para que lo capture importarProyecto


@login_required
def configurarToken(request):
    token_obj, _ = SonarToken.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = SonarTokenForm(request.POST, instance=token_obj)
        if form.is_valid():
            form.save()
            return redirect('token_guardado')  # Cambiar por la url que quieras
    else:
        form = SonarTokenForm(instance=token_obj)

    return render(request, "main/configurarToken.html", {"form": form})