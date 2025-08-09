from django.db import models


class Project(models.Model):
    id_project = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    key = models.CharField(max_length=100)
    last_analysis_sq = models.DateTimeField(blank=True, null=True)
    last_analysis_sm = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        managed = False
        db_table = 'projects'
