from django.db import models


# Create your models here.
class Metrics(models.Model):
    id = models.AutoField(primary_key=True, db_column='id_metric')
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=350)
    domain = models.CharField(max_length=50)
    tool = models.TextField()
    key = models.TextField()

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'metrics'


class Projects(models.Model):
    id = models.AutoField(primary_key=True, db_column='id_project')
    name = models.CharField(max_length=100)
    key = models.TextField()
    last_analysis_sq = models.DateTimeField()
    last_analysis_sm = models.DateTimeField()

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'projects'
