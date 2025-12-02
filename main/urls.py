"""
URL configuration for iscat project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.shortcuts import redirect
from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views

app_name = "main"

urlpatterns = [
    path("", views.homepage, name="home"),
    path("login/", views.login_view, name="login"),
    path("importarProyecto/", views.importarProyecto, name="importarProyecto"),
    path("logout/", auth_views.LogoutView.as_view(next_page='main:home'), name='logout'),
    path("configurarToken/", views.configurarToken, name="configurarToken"),
    path('proyecto/<int:project_id>/resultados/', views.ver_resultados, name='verResultados'),
    path('dashboardAnalisis/', views.dashboardAnalisis, name='dashboardAnalisis'),
    path('estado/', views.estado_herramientas, name='estado_herramientas'),
    # NUEVAS URLs para Celery
    path('monitorear-analisis/', views.monitorear_analisis, name='monitorear_analisis'),
    path('api/tarea/<str:task_id>/', views.verificar_tarea, name='verificar_tarea'),
    path('api/tareas-batch/', views.verificar_tareas_batch, name='verificar_tareas_batch'),
    path('proyecto/<int:project_id>/analizar/', views.analizar_proyecto_individual, name='analizar_proyecto_individual'),
    path('test-celery/', views.test_celery_view, name='test_celery'),
    path('analizar_sse/', views.analizar_sse, name='analizar_sse'),
]
