# iscat/__init__.py
"""
Inicialización del proyecto ISCAT
"""

# Esto asegura que Celery se cargue cuando Django inicia
from .celery import app as celery_app

__all__ = ('celery_app',)