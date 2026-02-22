# main/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import SonarToken


@receiver(post_save, sender=User)
def create_sonar_token(sender, instance, created, **kwargs):
    if created:
        try:
            from django.db import connection
            if 'sonar_token' in connection.introspection.table_names():
                SonarToken.objects.create(user=instance, token='')
        except Exception:
            pass  # Tabla no existe aún durante migraciones, se ignora


@receiver(post_save, sender=User)
def save_sonar_token(sender, instance, **kwargs):
    try:
        from django.db import connection
        if 'sonar_token' in connection.introspection.table_names():
            if hasattr(instance, 'sonartoken'):
                instance.sonartoken.save()
    except Exception:
        pass