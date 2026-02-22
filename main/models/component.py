from django.db import models


class Component(models.Model):
    id_component = models.AutoField(primary_key=True)
    id_project = models.ForeignKey('Project', models.DO_NOTHING, db_column='id_project')
    qualifier = models.CharField(max_length=10)
    path = models.CharField(max_length=250)
    key = models.CharField(max_length=500)

    def __str__(self):
        return self.path

    class Meta:
        managed = True
        db_table = 'components'