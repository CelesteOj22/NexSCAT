# main/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import SonarToken


@receiver(post_save, sender=User)
def create_sonar_token(sender, instance, created, **kwargs):
    if created:
        # Crea un registro en la tabla existente al crear un usuario
        SonarToken.objects.create(user=instance, token='')


@receiver(post_save, sender=User)
def save_sonar_token(sender, instance, **kwargs):
    if hasattr(instance, 'sonartoken'):
        instance.sonartoken.save()


