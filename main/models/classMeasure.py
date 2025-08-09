from django.db import models


class ClassMeasure(models.Model):
    id_clmeasure = models.AutoField(primary_key=True)
    id_metric = models.ForeignKey('Metric', models.DO_NOTHING, db_column='id_metric')
    id_class = models.ForeignKey('Class', models.DO_NOTHING, db_column='id_class')
    value = models.CharField(max_length=600, blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        managed = False
        db_table = 'class_measures'
