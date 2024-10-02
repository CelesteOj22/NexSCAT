from django.shortcuts import render
from django.contrib.auth.decorators import login_required
# para renderizar templates?
from django.http import HttpResponse
from .models import Metrics
from .models import Projects


# Create your views here.
def homepage(request):
    #print(Projects.objects.all().query)
    #print(Projects.objects.all())
    #metrics_query = Metrics.objects.all().query
    #print(metrics_query)
    #metrics1 = Metrics.objects.all()
    #print(metrics1)  # Verifica los resultados en la consola
    #parametros de render(request,template,content/data)
    return render(request=request, template_name="main/Index.html", context={"metrics": Metrics.objects.all})


def login(request):
    return render(request=request, template_name="registration/login.html")


#mi decorador va arriba de la definicion de la vista wuau
@login_required()
def importarProyecto(request):
    return render(request=request, template_name="main/importarProyecto.html")