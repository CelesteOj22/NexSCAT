from django.db import models


class Class(models.Model):
    id_class = models.AutoField(primary_key=True)
    id_component = models.ForeignKey('Component', models.DO_NOTHING, db_column='id_component')
    name = models.CharField()

    def __str__(self):
        return self.name

    class Meta:
        managed = False
        db_table = 'classes'