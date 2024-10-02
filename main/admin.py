from django.contrib import admin
from .models import Metrics
from .models import Projects

# Register your models here.

admin.site.register(Metrics)
admin.site.register(Projects)

