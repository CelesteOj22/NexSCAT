from django.db import models


class Metric(models.Model):
    id_metric = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=500, blank=True, null=True)
    domain = models.CharField(max_length=50, blank=True, null=True)
    tool = models.CharField(max_length=50, blank=True, null=True)
    key = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        managed = True
        db_table = 'metrics'