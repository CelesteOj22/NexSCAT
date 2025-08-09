from django.contrib import admin
from .models import Project, Metric, Component, ProjectMeasure, ComponentMeasure, Class, ClassMeasure

# Register your models here.

admin.site.register(Metric)
admin.site.register(Project)
admin.site.register(Component)
admin.site.register(ProjectMeasure)
admin.site.register(ComponentMeasure)
admin.site.register(Class)
admin.site.register(ClassMeasure)

