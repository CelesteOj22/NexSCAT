import subprocess
from .base import IHerramienta
import requests
from django.utils import timezone
from ..models import Project, Metric, ProjectMeasure


class SonarQube(IHerramienta):
    def __init__(self, binaries: str, host="http://localhost:9000"):
        self._sources = "."
        self._hosturl = host
        self._binaries = binaries

    def analizar(self, scanner, project_path: str):
        sep = project_path.split(sep='\\')
        project_key = self.normalizar_project_key(sep[-1])
        comando = (
            f'cd {project_path} && {scanner} '
            f'-Dsonar.projectKey={project_key} '
            f'-Dsonar.sources={self._sources} '
            f'-Dsonar.host.url={self._hosturl} '
            f'-Dsonar.java.binaries={self._binaries}'
        )

        try:
            print("Comenzando el analisis en SonarQube de " + project_key)
            stdout = subprocess.run(
                comando,
                stdout=subprocess.PIPE,
                universal_newlines=True,
                check=True,
                text=True,
                shell=True
            ).stdout

            if 'EXECUTION SUCCESS' in stdout:
                return f"✅ Proyecto {project_key} analizado con éxito en SonarQube"
            else:
                return f"⚠ Proyecto {project_key} analizado pero con advertencias"
        except Exception as e:
            return f"❌ Error analizando {project_key} en SonarQube: {e}"

    def procesar(self, project: Project, token=None):
        metric_keys = ",".join(Metric.objects.filter(tool="SonarQube").values_list("key", flat=True))
        url = f"{self._hosturl}/api/measures/component?component={project.key}&metricKeys={metric_keys}"

        auth = (token, "") if token else None
        response = requests.get(url, auth=auth)

        if response.status_code == 200:
            data = response.json()
            measures = data["component"]["measures"]

            for m in measures:
                metric_key = m["metric"]
                value = m["value"]

                try:
                    metric = Metric.objects.get(key=metric_key, tool="SonarQube")
                    ProjectMeasure.objects.update_or_create(
                        id_project=project,
                        id_metric=metric,
                        defaults={"value": str(value)}
                    )
                except Metric.DoesNotExist:
                    print(f"⚠ Métrica {metric_key} no encontrada en la tabla metrics (SonarQube)")

            # actualizamos timestamp en el proyecto
            project.last_analysis_sq = timezone.now()
            project.save(update_fields=["last_analysis_sq"])
        else:
            print("❌ Error consultando API SonarQube:", response.text)