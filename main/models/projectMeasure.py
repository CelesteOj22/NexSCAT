from django.db import models


class ProjectMeasure(models.Model):
    id_pmeasure = models.AutoField(primary_key=True)
    id_metric = models.ForeignKey('Metric', models.DO_NOTHING, db_column='id_metric')
    id_project = models.ForeignKey('Project', models.DO_NOTHING, db_column='id_project')
    value = models.CharField(max_length=80, blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        managed = True
        db_table = 'project_measures'