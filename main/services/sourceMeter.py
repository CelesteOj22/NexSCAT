import subprocess
from .base import IHerramienta
import openpyxl
from django.utils import timezone
from ..models import Project, Metric, ProjectMeasure

class SourceMeter(IHerramienta):
    def __init__(self, resultsDir: str):
        self._resultsDir = resultsDir
        self._runFB = 'true'
        self._FBFileList = 'filelist.txt'

    def analizar(self, source, project_path: str):
        sep = project_path.split(sep='\\')
        project_key = sep[-1]

        comando = (
            f'cd {project_path} && {source} '
            f'-projectName={project_key} '
            f'-projectBaseDir={project_path} '
            f'-resultsDir={self._resultsDir} '
            f'-runFB={self._runFB} '
            f'-FBFileList={self._FBFileList}'
        )

        try:
            subprocess.run(
                comando,
                stdout=subprocess.PIPE,
                universal_newlines=True,
                check=True,
                text=True,
                shell=True
            )
            return f"✅ Proyecto {project_key} analizado con éxito en SourceMeter"
        except Exception as e:
            return f"❌ Error analizando {project_key} en SourceMeter: {e}"

    def procesar(self, project: Project, xlsx_path: str):
        """
        Procesa el archivo XLSX generado por SourceMeter y guarda métricas en ProjectMeasure.
        """
        try:
            wb = openpyxl.load_workbook(xlsx_path, data_only=True)
            ws = wb.active

            # obtenemos todas las métricas conocidas de SourceMeter
            metrics_sm = {m.key: m for m in Metric.objects.filter(tool="SourceMeter")}

            for row in ws.iter_rows(min_row=2, values_only=True):
                metric_key = row[0]  # asumimos que la primer columna es el nombre de la métrica
                value = row[1]  # y la segunda el valor

                if metric_key in metrics_sm:
                    ProjectMeasure.objects.update_or_create(
                        id_project=project,
                        id_metric=metrics_sm[metric_key],
                        defaults={"value": str(value)}
                    )
                else:
                    print(f"⚠ Métrica {metric_key} no encontrada en tabla metrics (SourceMeter)")

            # actualizamos timestamp en el proyecto
            project.lastanalysissm = timezone.now()
            project.save(update_fields=["lastanalysissm"])

            print(f"✅ SourceMeter procesado para {project.name}")

        except Exception as e:
            print(f"❌ Error procesando SourceMeter XLSX: {e}")