import os
import pathlib

from django.shortcuts import render
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
# para renderizar templates?
from django.http import HttpResponse, JsonResponse
from django.utils import timezone

from .models import Metric, Project
from main.services.factory import sonar, source
from main.services import sonarQube,sourceMeter


# Create your views here.
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

        for proyecto in directorio.iterdir():
            analizarProyectos(str(proyecto))
        # resultado = analizar(path)

        return render(request, 'main/resultado.html', {
            'mensaje': f'Análisis de {path} completado correctamente.'
            # 'resultado': resultado
        })

    return render(request, 'main/importarProyecto.html')


def analizarProyectos(proyecto):
    project_name = pathlib.Path(proyecto).name

    # Alta del proyecto si no existe
    project, created = Project.objects.get_or_create(
        name=project_name,
        defaults={"path": proyecto}
    )

    if not created:
        print(f"📌 Proyecto {project_name} ya existía en la base")
    else:
        print(f"✅ Proyecto {project_name} creado en la base")

    resultados = {}

    # 🔹 Analizar y procesar con SonarQube
    resultado_sonar = sonar.analizar(settings.SONAR_SCANNER_PATH, proyecto)
    sonar.procesar(project, resultado_sonar)
    resultados["sonar"] = resultado_sonar

    # 🔹 Analizar y procesar con SourceMeter
    resultado_source = source.analizar(settings.SOURCEMETER_PATH, proyecto)
    source.procesar(project, resultado_source)
    resultados["sourcemeter"] = resultado_source

    project.save(update_fields=["lastanalysissm", "lastanalysissq"])

    return JsonResponse(resultados)
