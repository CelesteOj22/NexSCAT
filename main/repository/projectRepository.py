from ..models import Project
from datetime import datetime


def get_all_projects():
    return Project.objects.all()


def get_project(project_name):
    return Project.objects.filter(name__icontains=project_name).first()


# va a devolver:
# {"last_analysis_sq": datetime(2025, 8, 12, 15, 30, tzinfo=...),
# "last_analysis_sm": datetime(2025, 8, 11, 18, 45, tzinfo=...)}
# probar que como devuelve
def get_project_last_analysis(project_name):
    return Project.objects.filter(name__icontains=project_name).values("last_analysis_sq", "last_analysis_sm").first()


def project_exists(project_name):
    return Project.objects.filter(name__icontains=project_name).exists()


def insert_project(key, name, last_analysis, tool):
    if tool == "sm":
        Project.objects.create(
            key=key,
            name=name,
            lastAnalysissm=last_analysis
        )
    else:
        Project.objects.create(
            key=key,
            name=name,
            lastAnalysissq=last_analysis
        )


def update_project(project_name, last_analysis, tool):
    try:
        project = Project.objects.get(name__icontains=project_name)
        if tool == "sm":
            project.lastAnalysissm = last_analysis
        else:
            project.lastAnalysissq = last_analysis
        project.save()
    except Project.DoesNotExist:
        print("El proyecto no existe")
