# scat/celery.py
from celery import Celery
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scat.settings')

app = Celery('scat')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()