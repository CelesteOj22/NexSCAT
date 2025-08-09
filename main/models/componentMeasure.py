from django.db import models


class ComponentMeasure(models.Model):
    id_cmeasure = models.AutoField(primary_key=True)
    id_metric = models.ForeignKey('Metric', models.DO_NOTHING, db_column='id_metric')
    id_component = models.ForeignKey('Component', models.DO_NOTHING, db_column='id_component')
    value = models.CharField(max_length=80, blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        managed = False
        db_table = 'component_measures'