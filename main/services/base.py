from abc import ABC, abstractmethod

from main.models import Project


class IHerramienta(ABC):
    """Interfaz para herramientas de análisis de proyectos."""

    @abstractmethod
    def analizar(self, ejecutable: str, project_path: str) -> None:
        """
        Ejecuta el análisis sobre un proyecto con la herramienta concreta.

        :param analizador: Nombre de la herramienta
        :param projectName: Nombre del proyecto a analizar
        """
        pass

    @abstractmethod
    def procesar(self, project: Project, *args, **kwargs):
        """Procesa los resultados del análisis y guarda métricas en la BD."""
        pass
