from django.db import models


class Project(models.Model):
    id_project = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    key = models.CharField(max_length=100, blank=True, null=True)
    last_analysis_sq = models.DateTimeField(blank=True, null=True)
    last_analysis_sm = models.DateTimeField(blank=True, null=True)
    created_by = models.ForeignKey('auth.User', models.DO_NOTHING, db_column='created_by')
    created_at = models.DateTimeField(auto_now_add=True)  # se completa solo
    path = models.CharField(max_length=500, blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        managed = False
        db_table = 'projects'
