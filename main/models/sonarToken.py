# main/models/sonarToken.py
from django.db import models
from django.contrib.auth.models import User


class SonarToken(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, db_column='user_id', on_delete=models.CASCADE)
    token = models.CharField(max_length=255, blank=True)  # puede empezar vacío
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - Token"

    class Meta:
        managed = True
        db_table = 'sonar_token'
