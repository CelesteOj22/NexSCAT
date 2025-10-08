from abc import ABC, abstractmethod
import re
import subprocess
from main.models import Project



class IHerramienta(ABC):
    """Interfaz para herramientas de análisis de proyectos."""

    @abstractmethod
    def analizar(self, ejecutable: str, project_path: str, token: None) -> None:
        """
        Ejecuta el análisis sobre un proyecto con la herramienta concreta.

        :param ejecutable: Nombre de la herramienta
        :param project_path: Path del proyecto a analizar
        :param token: token de user de sonarQbue
        """
        pass

    @abstractmethod
    def procesar(self, project: Project, *args, **kwargs):
        """Procesa los resultados del análisis y guarda métricas en la BD."""
        pass

    def normalizar_project_key(self, nombre: str) -> str:
        """
        Normaliza un nombre de proyecto para usarlo como project_key válido
        en herramientas como SonarQube o SourceMeter.

        Reglas:
          - minúsculas
          - permite solo [a-z0-9._:-]
          - reemplaza cualquier otro caracter por "_"
        """
        key = nombre.lower()
        key = re.sub(r'[^a-z0-9._:-]', '_', key)
        key = key if key else "proyecto"
        return f"nexscat:{key}"

    def start_sonarqube(self, sonar_path):
        # Arranca el proceso (no bloqueante)
        process = subprocess.Popen(
            [f"{sonar_path}/bin/windows-x86-64/StartSonar.bat"],
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return process

    @abstractmethod
    def is_up(self, token: str = None) -> bool:
        """Verifica si la herramienta está disponible para análisis."""
        pass