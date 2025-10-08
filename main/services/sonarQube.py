import logging
import subprocess
import time
from pathlib import Path
import requests
from django.utils import timezone
from ..models import Project, Metric, ProjectMeasure
from .base import IHerramienta

logger = logging.getLogger(__name__)


class SonarQube(IHerramienta):
    def __init__(self, binaries: str, host="http://127.0.0.1:9000"):
        self._sources = "."
        self._hosturl = host
        self._binaries = binaries

    def analizar(self, scanner, project_path: str, token: str):
        project_path = Path(project_path)
        project_key = self.normalizar_project_key(project_path.name)

        # Construir lista de argumentos
        comando = [
            scanner,
            f"-Dsonar.projectKey={project_key}",
            f"-Dsonar.sources={self._sources}",
            f"-Dsonar.host.url={self._hosturl}",
            f"-Dsonar.token={token}"
        ]

        # 🔹 Detectar directorios compilados automáticamente
        binaries_dirs = []
        common_bin_paths = [
            "target/classes",
            "build/classes/java/main",
            "build/classes",
            "bin",
            "out/production",
            "classes"
        ]

        for bin_path in common_bin_paths:
            full_path = project_path / bin_path
            if full_path.exists() and full_path.is_dir():
                binaries_dirs.append(str(full_path))

        # Si encontramos binaries, los usamos; si no, usamos el directorio raíz
        if binaries_dirs:
            comando.append(f"-Dsonar.java.binaries={','.join(binaries_dirs)}")
            print(f"📁 Usando binaries: {', '.join(binaries_dirs)}")
        elif self._binaries:
            comando.append(f"-Dsonar.java.binaries={self._binaries}")
            print(f"📁 Usando binaries configurados: {self._binaries}")
        else:
            # 🔹 CRÍTICO: Usar "." en lugar de nada evita el error
            comando.append(f"-Dsonar.java.binaries=.")
            print(f"📁 No se encontraron binaries, usando directorio raíz")

        # 🔹 Exclusiones para optimizar
        exclusiones = [
            "**/test/**",
            "**/tests/**",
            "**/*Test.java",
            "**/*Tests.java",
            "**/target/**",
            "**/build/**",
            "**/node_modules/**",
            "**/.git/**",
            "**/.svn/**"
        ]
        comando.append(f"-Dsonar.exclusions={','.join(exclusiones)}")

        # 🔹 Timeouts y optimizaciones
        comando.extend([
            "-Dsonar.ws.timeout=300",
            "-Dsonar.scm.disabled=true"
        ])

        comando.append("-X")

        # 🔹 Variables de entorno para más memoria
        import os
        env = os.environ.copy()
        env['SONAR_SCANNER_OPTS'] = '-Xmx2048m -XX:MaxMetaspaceSize=512m'

        try:
            print(f"🔍 Comenzando el análisis en SonarQube de {project_key}")

            result = subprocess.run(
                comando,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                check=True,
                cwd=project_path,
                env=env  # 🔹 Agregar entorno con más memoria
            )

            stdout = result.stdout

            if 'EXECUTION SUCCESS' in stdout:
                return True, f"✅ Proyecto {project_key} analizado con éxito"
            else:
                return False, f"⚠ Proyecto {project_key} analizado pero con advertencias:\n{stdout}"

        except subprocess.CalledProcessError as e:
            error_msg = f"❌ Error analizando {project_key}:\n{e.stdout}"

            # Sugerencias según el error
            if "No files nor directories matching" in e.stdout:
                print("💡 El proyecto no tiene directorios compilados (esto es normal para análisis de fuentes)")
            elif "OutOfMemoryError" in e.stdout:
                print("💡 Aumenta la memoria: SONAR_SCANNER_OPTS='-Xmx3072m'")

            return False, error_msg

    def esperar_analisis_completo(self, project_key: str, token: str, timeout: int = 300, interval: int = 10):
        """
        Espera hasta que el análisis más reciente esté completamente procesado en SonarQube.

        Args:
            project_key: Clave del proyecto
            token: Token de autenticación
            timeout: Tiempo máximo de espera en segundos (default: 5 minutos)
            interval: Intervalo entre verificaciones en segundos (default: 10 segundos)

        Returns:
            bool: True si el análisis está completo, False si se agotó el timeout
        """
        print(f"🔍 Verificando estado del análisis para {project_key}...")

        start_time = time.time()

        while (time.time() - start_time) < timeout:
            if self._is_project_ready(project_key, token):
                print(f"✅ Proyecto {project_key} listo para consultar métricas")
                return True

            print(f"⏳ Proyecto {project_key} aún procesándose... esperando {interval}s")
            time.sleep(interval)

        print(f"⚠️ Timeout alcanzado esperando análisis de {project_key}")
        return False

    def _is_project_ready(self, project_key: str, token: str) -> bool:
        """
        Verifica si el último análisis del proyecto ya terminó en SonarQube
        y que las métricas básicas estén disponibles.
        Maneja proyectos nuevos y existentes, y tareas fallidas.
        """
        try:
            # 1. Consultar la última tarea CE (Compute Engine) asociada al proyecto
            ce_url = f"{self._hosturl}/api/ce/component?component={project_key}"
            response = requests.get(ce_url, auth=(token, ""))

            if response.status_code != 200:
                print(f"❌ Error consultando CE para {project_key}: {response.status_code}")
                return False

            ce_data = response.json()
            task = ce_data.get("current")
            if not task:
                queue = ce_data.get("queue", [])
                task = queue[0] if queue else None

            if not task:
                print(f"🔍 No se encontraron tareas CE para {project_key}")
                return False

            status = task.get("status")

            if status == "FAILED":
                print(f"❌ La última tarea de {project_key} falló. Revisar Background Tasks en SonarQube")
                return False
            elif status == "CANCELED":
                print(f"❌ La última tarea de {project_key} fue cancelada. Revisar Background Tasks en SonarQube")
                return False
            elif status != "SUCCESS":
                print(f"⏳ Última tarea de {project_key} aún en estado {status}")
                return False

            # 2. Confirmar que ya hay métricas básicas disponibles
            return self._check_basic_metrics_available(project_key, token)

        except Exception as e:
            print(f"❌ Error verificando estado del proyecto {project_key}: {e}")
            return False

    def _check_basic_metrics_available(self, project_key: str, token: str) -> bool:
        """
        Verifica que las métricas básicas estén disponibles
        """
        try:
            # Verificar métricas básicas que siempre deberían estar
            basic_metrics = "ncloc,lines,files"
            url = f"{self._hosturl}/api/measures/component?component={project_key}&metricKeys={basic_metrics}"

            response = requests.get(url, auth=(token, ""))

            if response.status_code != 200:
                return False

            data = response.json()
            measures = data.get("component", {}).get("measures", [])

            # Si tiene al menos 2 de las 3 métricas básicas, consideramos que está listo
            if len(measures) >= 2:
                print(f"✅ Métricas básicas disponibles para {project_key}")
                return True
            else:
                print(f"🔍 Solo {len(measures)} métricas básicas disponibles para {project_key}")
                return False

        except Exception as e:
            print(f"❌ Error verificando métricas básicas para {project_key}: {e}")
            return False

    def procesar(self, project: Project, token: str, project_key: str):
        print("🔄 Iniciando procesamiento de métricas...")

        # Primero esperar a que el análisis esté completo
        if not self.esperar_analisis_completo(project_key, token):
            print(f"⚠️ No se pudo verificar que el análisis esté completo para {project_key}")
            print("🔄 Intentando procesar métricas de todos modos...")

        # Obtener todas las métricas de la BD
        metricas_bd = list(Metric.objects.filter(tool="SonarQube"))
        total_metricas = len(metricas_bd)
        metricas_procesadas = 0
        metricas_fallidas = []

        print(f"📋 {total_metricas} métricas configuradas en BD")

        # Procesar métricas en lotes de 20
        lote_size = 20

        for i in range(0, total_metricas, lote_size):
            lote = metricas_bd[i:i + lote_size]
            lote_keys = [m.key for m in lote]

            print(f"🔄 Procesando lote {i // lote_size + 1}: {len(lote_keys)} métricas")

            metric_keys_str = ",".join(lote_keys)
            url = f"{self._hosturl}/api/measures/component?component={project_key}&metricKeys={metric_keys_str}"

            try:
                auth = (token, "")
                response = requests.get(url, auth=auth, timeout=30)

                if response.status_code == 200:
                    data = response.json()
                    component = data.get("component", {})
                    measures = component.get("measures", [])

                    if measures:
                        metric_objects_map = {obj.key: obj for obj in lote}
                        metricas_encontradas = set()

                        for measure in measures:
                            metric_key = measure.get("metric")
                            value = measure.get("value")

                            if not metric_key or value is None:
                                continue

                            metricas_encontradas.add(metric_key)

                            if metric_key in metric_objects_map:
                                try:
                                    ProjectMeasure.objects.update_or_create(
                                        id_project=project,
                                        id_metric=metric_objects_map[metric_key],
                                        defaults={"value": str(value)}
                                    )
                                    metricas_procesadas += 1
                                    print(f"   ✅ {metric_key}: {value}")
                                except Exception as e:
                                    print(f"   ⚠️ Error guardando {metric_key}: {e}")
                                    metricas_fallidas.append(metric_key)

                        no_encontradas = [obj.key for obj in lote if obj.key not in metricas_encontradas]
                        metricas_fallidas.extend(no_encontradas)

                        if no_encontradas:
                            print(f"   ⚠️ {len(no_encontradas)} métricas no disponibles en este lote")
                    else:
                        print(f"   ⚠️ No se encontraron métricas en este lote")
                        metricas_fallidas.extend(lote_keys)

                elif response.status_code == 404:
                    print(f"   ⚠️ Error 404 en lote {i // lote_size + 1}, procesando individualmente...")

                    for metric_obj in lote:
                        try:
                            url_individual = f"{self._hosturl}/api/measures/component?component={project_key}&metricKeys={metric_obj.key}"
                            response_individual = requests.get(url_individual, auth=auth, timeout=10)

                            if response_individual.status_code == 200:
                                data_individual = response_individual.json()
                                component_individual = data_individual.get("component", {})
                                measures_individual = component_individual.get("measures", [])

                                if measures_individual:
                                    measure = measures_individual[0]
                                    value = measure.get("value")

                                    if value is not None:
                                        ProjectMeasure.objects.update_or_create(
                                            id_project=project,
                                            id_metric=metric_obj,
                                            defaults={"value": str(value)}
                                        )
                                        metricas_procesadas += 1
                                        print(f"   ✅ {metric_obj.key}: {value}")
                                    else:
                                        metricas_fallidas.append(metric_obj.key)
                                else:
                                    metricas_fallidas.append(metric_obj.key)
                            else:
                                metricas_fallidas.append(metric_obj.key)

                        except Exception as e:
                            print(f"   ⚠️ Error procesando {metric_obj.key}: {e}")
                            metricas_fallidas.append(metric_obj.key)
                else:
                    print(f"   ❌ Error HTTP {response.status_code} en lote {i // lote_size + 1}")
                    metricas_fallidas.extend(lote_keys)

            except requests.RequestException as e:
                print(f"   ❌ Error de conexión en lote {i // lote_size + 1}: {e}")
                metricas_fallidas.extend(lote_keys)
            except Exception as e:
                print(f"   ❌ Error inesperado en lote {i // lote_size + 1}: {e}")
                metricas_fallidas.extend(lote_keys)

        # Mostrar resumen
        print(f"\n📊 Resumen del procesamiento:")
        print(f"   ✅ Métricas procesadas: {metricas_procesadas}")
        print(f"   ⚠️ Métricas no disponibles: {len(metricas_fallidas)}")

        if metricas_fallidas and len(metricas_fallidas) <= 10:
            print(f"   📝 Métricas no disponibles: {', '.join(metricas_fallidas)}")
        elif len(metricas_fallidas) > 10:
            print(f"   📝 Primeras no disponibles: {', '.join(metricas_fallidas[:10])}...")

        if metricas_procesadas > 0:
            project.last_analysis_sq = timezone.now()
            project.save(update_fields=["last_analysis_sq"])
            print(f"\n✅ Procesamiento completado: {metricas_procesadas} métricas guardadas")
        else:
            print(f"\n⚠️ No se pudieron procesar métricas para {project_key}")

    def procesar_con_reintentos(self, project: Project, token: str, project_key: str, max_reintentos: int = 3):
        """
        Procesa las métricas con reintentos si no están disponibles
        Ahora usa el procesamiento resiliente que se salta métricas problemáticas
        """
        for intento in range(max_reintentos):
            try:
                print(f"🔄 Intento {intento + 1}/{max_reintentos} procesando métricas...")
                self.procesar(project, token, project_key)
                return True
            except Exception as e:
                print(f"❌ Error en intento {intento + 1}: {e}")
                if intento < max_reintentos - 1:
                    wait_time = (intento + 1) * 20  # Esperar 20s, 40s, 60s
                    print(f"⏳ Esperando {wait_time}s antes del siguiente intento...")
                    time.sleep(wait_time)
                else:
                    print(f"❌ Falló después de {max_reintentos} intentos")
                    # No lanzar excepción - el procesamiento resiliente ya manejó lo que pudo
                    print("⚠️ Continuando con las métricas que se pudieron procesar...")
                    return False

        return True

    def is_up(self, token: str = None) -> bool:
        try:
            url = f"{self._hosturl}/api/system/health"
            if token:
                response = requests.get(url, auth=(token, ""))
            else:
                response = requests.get(url)
            if response.status_code == 200:
                data = response.json()
                return data.get("health", "").upper() == "GREEN"
            else:
                logger.warning(f"{self.__class__.__name__} returned status {response.status_code}")
                return False
        except requests.RequestException as e:
            logger.error(f"No se pudo contactar {self.__class__.__name__}: {e}")
            return False

    def check_tool_status(self, tool: IHerramienta, token: str = None):
        """
        Lanza excepción si la herramienta no está disponible.
        """
        if not tool.is_up(token):
            raise Exception(f"{tool.__class__.__name__} no está disponible para análisis.")