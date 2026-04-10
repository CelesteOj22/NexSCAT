#services/sourceMeter.py
import os
import platform as platform_module
import shutil
import subprocess
import time
import csv
from pathlib import Path

from django.conf import settings

from .base import IHerramienta
from django.utils import timezone
from ..models import Project, Metric, ProjectMeasure, Component, ComponentMeasure, Class, ClassMeasure


class SourceMeter(IHerramienta):
    def __init__(self, resultsDir: str = None):
        self._runFB = 'true'
        self._FBFileList = 'filelist.txt'
    
    def _get_java11_env(self):
        env = os.environ.copy()
        java11_home = os.environ.get('JAVA11_HOME', '/usr/lib/jvm/temurin-11-jdk-amd64')
        env['JAVA_HOME'] = java11_home
        # Poner java11/bin ANTES que /usr/bin en el PATH
        # Y agregar override para que /usr/bin/java sea ignorado
        env['PATH'] = f"{java11_home}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        return env

    def analizar(self, source, project_path: str, project_name: str):
        """
        Analiza un proyecto Java con SourceMeter

        Args:
            source: Path al ejecutable de SourceMeter (ej: AnalyzerJava)
            project_path: Path al proyecto a analizar
            project_name: Nombre del proyecto

        Returns:
            tuple: (success: bool, message: str)
        """
        project_path = Path(project_path)
        project_key = self.normalizar_project_key(project_name)

        if not project_path.exists():
            return False, f"❌ El directorio {project_path} no existe"

        # FIX: usar /tmp para evitar cross-device link entre volúmenes Docker
        #results_base = project_path / "SMResults"
        results_base = Path(f"/app/proyectos/{project_name}/SMResults")
        results_base.mkdir(parents=True, exist_ok=True)

        comando = [
            source,
            f"-projectName={project_name}",
            f"-projectBaseDir={str(project_path)}",
            f"-resultsDir={str(results_base)}",
            f"-runFB={self._runFB}",
            f"-FBFileList={self._FBFileList}"
        ]

        # FIX: usar Java 11 para SourceMeter (requiere exactamente Java 11)
        java11_env = self._get_java11_env()
        print(f"☕ SourceMeter usando JAVA_HOME: {java11_env.get('JAVA_HOME')}")

        try:
            result = subprocess.run(
                comando,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                check=True,
                cwd=project_path,
                env=java11_env  # ✅ entorno con Java 11
            )

            stdout = result.stdout
            print(f"✅ Proceso de SourceMeter terminó para {project_key}")

            # Verificar archivos generados
            analysis_dir = self._buscar_directorio_analisis(project_path, project_name)
            if analysis_dir:
                print(f"✅ Proyecto {project_key} analizado con éxito")
                print(f"📁 Análisis en: {analysis_dir}")
                return True, f"✅ Proyecto {project_key} analizado con éxito en SourceMeter"
            else:
                print(f"⚠️ No se encontró directorio de análisis")
                return False, f"⚠️ No se encontraron archivos de resultados"

        except subprocess.CalledProcessError as e:
            error_msg = f"❌ Error analizando {project_key}:\n{e.stdout[-500:]}"
            print(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"❌ Error inesperado: {e}"
            print(error_msg)
            return False, error_msg

    def _buscar_directorio_analisis(self, project_path: Path, project_name: str) -> Path:
        """
        Busca el directorio de análisis más reciente
        Ruta: project_path/SMResults/project_name/java/TIMESTAMP/
        """
        #results_base = project_path / "SMResults" / project_name / "java"
        #FIX: buscar en /tmp donde realmente se guardan los resultados
        results_base = Path(f"/app/proyectos/{project_name}/SMResults/java")
        print(f"RESULT BASE {results_base}")
        if not results_base.exists():
            print(f"❌ No existe {results_base}")
            return None

        # Buscar carpetas de timestamp
        timestamp_dirs = [d for d in results_base.iterdir() if d.is_dir()]

        if not timestamp_dirs:
            print(f"❌ No hay análisis en {results_base}")
            return None

        # Tomar el más reciente
        timestamp_dirs.sort(reverse=True)
        latest_dir = timestamp_dirs[0]

        print(f"📁 Usando análisis: {latest_dir.name}")
        return latest_dir

    def procesar(self, project: Project, project_name: str):
        """
        Procesa todos los niveles: Project, Components (packages) y Classes

        Args:
            project: Instancia del modelo Project
            project_name: NOMBRE del proyecto SIN normalizar (ej: checkstyle-4.3)
        """
        print("🔄 Iniciando procesamiento de SourceMeter...")

        project_path = Path(project.path)
        analysis_dir = self._buscar_directorio_analisis(project_path, project_name)

        if not analysis_dir:
            print(f"❌ No se puede procesar: directorio de análisis no encontrado")
            return

        total_procesadas = 0

        # 1. Procesar métricas a nivel PROJECT (Component.csv)
        print("\n📊 Procesando nivel PROJECT...")
        component_csv = analysis_dir / f"{project.name}-Component.csv"
        if component_csv.exists():
            n = self._procesar_project_level(project, component_csv)
            total_procesadas += n
            print(f"✅ {n} métricas de proyecto procesadas")
        else:
            print(f"⚠️ No se encontró {component_csv.name}")

        # 2. Procesar COMPONENTS/Packages (Package.csv)
        print("\n📦 Procesando nivel PACKAGE/COMPONENT...")
        package_csv = analysis_dir / f"{project.name}-Package.csv"
        if package_csv.exists():
            n = self._procesar_package_level(project, package_csv)
            total_procesadas += n
            print(f"✅ {n} componentes procesados")
        else:
            print(f"⚠️ No se encontró {package_csv.name}")

        # 3. Procesar CLASSES (Class.csv)
        print("\n🏛️ Procesando nivel CLASS...")
        class_csv = analysis_dir / f"{project.name}-Class.csv"
        if class_csv.exists():
            n = self._procesar_class_level(project, class_csv)
            total_procesadas += n
            print(f"✅ {n} clases procesadas")
        else:
            print(f"⚠️ No se encontró {class_csv.name}")

        if total_procesadas > 0:
            project.last_analysis_sm = timezone.now()
            project.save(update_fields=["last_analysis_sm"])
            print(f"\n✅ Procesamiento SourceMeter completado: {total_procesadas} elementos procesados")
        else:
            print(f"\n⚠️ No se procesaron datos")

    def _procesar_project_level(self, project: Project, csv_path: Path) -> int:
        """
        Procesa el CSV de Component (métricas a nivel proyecto)
        Solo tiene 1 fila con métricas del proyecto completo
        Guarda en: ProjectMeasure
        """
        try:
            metrics_sm = {m.key: m for m in Metric.objects.filter(tool="SourceMeter")}
            procesadas = 0

            with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)

                # Component.csv tiene solo 1 fila
                row = next(reader, None)
                if not row:
                    print("⚠️ CSV vacío")
                    return 0

                print(f"📋 Columnas disponibles: {len(reader.fieldnames)}")

                # Para cada métrica de la BD, buscar su valor en el CSV
                for metric_key, metric_obj in metrics_sm.items():
                    if metric_key in row:
                        value = row[metric_key].strip()

                        if value and value != '':
                            try:
                                ProjectMeasure.objects.update_or_create(
                                    id_project=project,
                                    id_metric=metric_obj,
                                    defaults={"value": value}
                                )
                                procesadas += 1
                                print(f"   ✅ {metric_key}: {value}")
                            except Exception as e:
                                print(f"   ⚠️ Error guardando {metric_key}: {e}")

            return procesadas

        except Exception as e:
            print(f"❌ Error procesando Component.csv: {e}")
            return 0

    def _procesar_package_level(self, project: Project, csv_path: Path) -> int:
        """
        Procesa el CSV de Package (métricas por paquete)
        Cada fila = un paquete
        Guarda en: Component + ComponentMeasure
        """
        try:
            metrics_sm = {m.key: m for m in Metric.objects.filter(tool="SourceMeter")}
            componentes_creados = 0

            with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    # Obtener nombre del paquete
                    package_name = row.get('Name', '').strip()
                    package_path = row.get('LongName', package_name).strip()

                    if not package_name:
                        continue

                    # Crear o recuperar el Component (paquete)
                    component, created = Component.objects.get_or_create(
                        id_project=project,
                        key=f"{project.key}:{package_path}",
                        defaults={
                            "qualifier": "PKG",  # Package
                            "path": package_path
                        }
                    )

                    if created:
                        componentes_creados += 1

                    # Guardar métricas del paquete
                    for metric_key, metric_obj in metrics_sm.items():
                        if metric_key in row:
                            value = row[metric_key].strip()

                            if value and value != '':
                                try:
                                    ComponentMeasure.objects.update_or_create(
                                        id_component=component,
                                        id_metric=metric_obj,
                                        defaults={"value": value}
                                    )
                                except Exception as e:
                                    print(f"   ⚠️ Error guardando métrica {metric_key} para {package_name}: {e}")

                print(f"   📦 {componentes_creados} paquetes nuevos creados")
                return componentes_creados

        except Exception as e:
            print(f"❌ Error procesando Package.csv: {e}")
            return 0

    def _procesar_class_level(self, project: Project, csv_path: Path) -> int:
        """
        Procesa el CSV de Class (métricas por clase)
        Cada fila = una clase
        Guarda en: Class + ClassMeasure
        """
        try:
            metrics_sm = {m.key: m for m in Metric.objects.filter(tool="SourceMeter")}
            clases_creadas = 0

            with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    # Obtener información de la clase
                    class_name = row.get('Name', '').strip()
                    class_long_name = row.get('LongName', class_name).strip()
                    parent_name = row.get('Parent', '').strip()  # Nombre del paquete

                    if not class_name:
                        continue

                    # Buscar o crear el Component (paquete) padre
                    component = None
                    if parent_name:
                        try:
                            component = Component.objects.get(
                                id_project=project,
                                key=f"{project.key}:{parent_name}"
                            )
                        except Component.DoesNotExist:
                            # Crear el componente si no existe
                            component = Component.objects.create(
                                id_project=project,
                                key=f"{project.key}:{parent_name}",
                                qualifier="PKG",
                                path=parent_name
                            )

                    if not component:
                        # Si no hay paquete padre, crear uno "default"
                        component, _ = Component.objects.get_or_create(
                            id_project=project,
                            key=f"{project.key}:default",
                            defaults={
                                "qualifier": "PKG",
                                "path": "(default package)"
                            }
                        )

                    # Crear o recuperar la Class
                    class_obj, created = Class.objects.get_or_create(
                        id_component=component,
                        name=class_long_name,  # Usar long name para unicidad
                        defaults={}
                    )

                    if created:
                        clases_creadas += 1

                    # Guardar métricas de la clase
                    metricas_guardadas = 0
                    for metric_key, metric_obj in metrics_sm.items():
                        if metric_key in row:
                            value = row[metric_key].strip()

                            if value and value != '':
                                try:
                                    ClassMeasure.objects.update_or_create(
                                        id_class=class_obj,
                                        id_metric=metric_obj,
                                        defaults={"value": value}
                                    )
                                    metricas_guardadas += 1
                                except Exception as e:
                                    print(f"   ⚠️ Error guardando métrica {metric_key} para {class_name}: {e}")

                print(f"   🏛️ {clases_creadas} clases nuevas creadas")
                return clases_creadas

        except Exception as e:
            print(f"❌ Error procesando Class.csv: {e}")
            import traceback
            traceback.print_exc()
            return 0

    def procesar_con_reintentos(self, project: Project, project_name: str, max_reintentos: int = 3):
        """Procesa con reintentos"""
        for intento in range(max_reintentos):
            try:
                print(f"🔄 Intento {intento + 1}/{max_reintentos} procesando SourceMeter...")
                self.procesar(project, project_name)
                return True
            except Exception as e:
                print(f"❌ Error en intento {intento + 1}: {e}")
                if intento < max_reintentos - 1:
                    time.sleep((intento + 1) * 10)
                else:
                    return False
        return True

    def is_up(self, token: str = None) -> bool:
        """
        Verifica que SourceMeter esté disponible
        Busca primero en PATH, luego en la ruta configurada en settings.py
        """
        # 1. Intentar encontrar en PATH (si está como variable de entorno)
        executable = "AnalyzerJava" if platform_module.system() == "Linux" else "SourceMeterJava"
        if shutil.which(executable) is not None:
            print("✅ SourceMeter encontrado en PATH del sistema")
            return True

        # 2. Verificar la ruta configurada en settings.py
        sourcemeter_path = getattr(settings, 'SOURCEMETER_PATH', None)

        if sourcemeter_path:
            path_obj = Path(sourcemeter_path)

            if path_obj.exists():
                print(f"SourceMeter encontrado en: {sourcemeter_path}")
                return True
            else:
                print(f"SourceMeter configurado pero no encontrado en: {sourcemeter_path}")
        else:
            print("SOURCEMETER_PATH no está configurado en settings.py")

        # 3. No se encontró en ningún lado
        print("SourceMeter no está disponible")
        print("Sugerencias:")
        print("- Agregar SourceMeter al PATH del sistema")
        print("- Verificar la ruta en settings.py")
        print("- Instalar SourceMeter si no está instalado")

        return False
