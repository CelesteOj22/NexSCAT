# iscat/config.py
"""
Configuración adaptativa según recursos del sistema
Detecta automáticamente CPU, RAM y entorno para optimizar rendimiento
"""
import os
import sys
import psutil
import logging

logger = logging.getLogger(__name__)


# ============================================
# DETECCIÓN DE ENTORNO
# ============================================
def is_docker():
    """Detecta si está corriendo en Docker"""
    return os.path.exists('/.dockerenv') or os.environ.get('RUNNING_IN_DOCKER', False)


def is_windows():
    """Detecta si está en Windows"""
    return sys.platform.startswith('win')


def is_linux():
    """Detecta si está en Linux"""
    return sys.platform.startswith('linux')


# ============================================
# DETECCIÓN DE RECURSOS
# ============================================
def get_system_ram_gb():
    """Obtiene RAM total del sistema en GB"""
    try:
        return psutil.virtual_memory().total / (1024 ** 3)
    except Exception as e:
        logger.warning(f"No se pudo detectar RAM: {e}")
        return 4  # Default conservador


def get_available_ram_gb():
    """Obtiene RAM disponible actual en GB"""
    try:
        return psutil.virtual_memory().available / (1024 ** 3)
    except Exception as e:
        logger.warning(f"No se pudo detectar RAM disponible: {e}")
        return 2


def get_cpu_count():
    """Obtiene cantidad de CPUs lógicos"""
    try:
        return psutil.cpu_count(logical=True) or 2
    except Exception as e:
        logger.warning(f"No se pudo detectar CPUs: {e}")
        return 2


def get_physical_cpu_count():
    """Obtiene cantidad de CPUs físicos"""
    try:
        return psutil.cpu_count(logical=False) or 1
    except Exception as e:
        return 1


# ============================================
# CÁLCULO INTELIGENTE DE WORKERS
# ============================================
def get_optimal_workers():
    """
    Determina automáticamente cuántos workers usar
    Considera RAM, CPUs y deja recursos libres para el SO

    Regla: Usar el MENOR entre:
    - CPUs disponibles
    - RAM / 2GB (cada worker usa ~2GB con SonarQube)
    - Máximo absoluto de 10 workers
    """
    total_ram_gb = get_system_ram_gb()
    cpu_count = get_cpu_count()

    # Calcular basado en RAM (dejar 2GB para el SO)
    ram_based_workers = max(1, int((total_ram_gb - 2) / 2))

    # Calcular basado en CPUs (dejar 1 CPU libre)
    cpu_based_workers = max(1, cpu_count - 1)

    # Usar el menor (cuello de botella)
    optimal = min(ram_based_workers, cpu_based_workers)

    # Límite absoluto de seguridad
    MAX_WORKERS = 10
    optimal = min(optimal, MAX_WORKERS)

    logger.debug(f"Recursos detectados: {total_ram_gb:.1f}GB RAM, {cpu_count} CPUs")
    logger.debug(f"Workers calculados: RAM-based={ram_based_workers}, CPU-based={cpu_based_workers}")
    logger.debug(f"Workers óptimos: {optimal}")

    return optimal


def get_sonarqube_memory_limits(total_ram_gb):
    """
    Calcula límites de memoria para SonarQube según RAM disponible

    Returns:
        tuple: (heap_size_mb, min_heap_mb) para -Xmx y -Xms
    """
    if total_ram_gb < 4:
        return (256, 128)  # Muy limitado
    elif total_ram_gb < 8:
        return (512, 128)  # AWS t3.medium
    elif total_ram_gb < 12:
        return (1024, 256)  # AWS t3.large
    elif total_ram_gb < 16:
        return (1536, 512)  # Desarrollo
    elif total_ram_gb < 32:
        return (2048, 512)  # Local potente
    else:
        return (3072, 1024)  # Workstation


# ============================================
# CLASE DE CONFIGURACIÓN
# ============================================
class AnalysisConfig:
    """Configuración de análisis según entorno"""

    # Detección de entorno
    IS_DOCKER = is_docker()
    IS_WINDOWS = is_windows()
    IS_LINUX = is_linux()

    # Recursos del sistema
    TOTAL_RAM_GB = get_system_ram_gb()
    AVAILABLE_RAM_GB = get_available_ram_gb()
    CPU_COUNT = get_cpu_count()
    PHYSICAL_CPU_COUNT = get_physical_cpu_count()

    # Modo de operación (se puede override con env var)
    MODE = os.environ.get('SCAT_MODE', 'auto').lower()

    # ============================================
    # CONFIGURACIÓN POR MODO
    # ============================================

    if MODE == 'production':
        # AWS / Cloud - Recursos limitados - Análisis secuencial
        MAX_PARALLEL_ANALYSIS = 1
        CELERY_WORKERS = 1
        ENABLE_PARALLEL = False
        USE_CELERY = False

        # Timeouts (en segundos)
        ANALYSIS_TIMEOUT = 600  # 10 minutos total
        SONARQUBE_TIMEOUT = 300  # 5 minutos para Sonar
        SOURCEMETER_TIMEOUT = 300  # 5 minutos para Source

        # SonarQube memory
        SONAR_HEAP_MB, SONAR_MIN_HEAP_MB = 512, 128

    elif MODE == 'development':
        # Local - Desarrollo con recursos moderados
        MAX_PARALLEL_ANALYSIS = 2
        CELERY_WORKERS = 2
        ENABLE_PARALLEL = True
        USE_CELERY = True

        ANALYSIS_TIMEOUT = 1200
        SONARQUBE_TIMEOUT = 600
        SOURCEMETER_TIMEOUT = 600

        SONAR_HEAP_MB, SONAR_MIN_HEAP_MB = 1024, 256

    elif MODE == 'balanced':
        # Intermedio - Balance entre rendimiento y recursos
        workers = min(get_optimal_workers(), 4)  # Máximo 4
        MAX_PARALLEL_ANALYSIS = workers
        CELERY_WORKERS = workers
        ENABLE_PARALLEL = workers > 1
        USE_CELERY = workers > 1

        ANALYSIS_TIMEOUT = 1500
        SONARQUBE_TIMEOUT = 900
        SOURCEMETER_TIMEOUT = 600

        SONAR_HEAP_MB, SONAR_MIN_HEAP_MB = get_sonarqube_memory_limits(TOTAL_RAM_GB)

    elif MODE == 'performance':
        # Local - Máximo rendimiento
        workers = get_optimal_workers()
        MAX_PARALLEL_ANALYSIS = workers
        CELERY_WORKERS = workers
        ENABLE_PARALLEL = True
        USE_CELERY = True

        ANALYSIS_TIMEOUT = 1800  # 30 minutos
        SONARQUBE_TIMEOUT = 1200  # 20 minutos
        SOURCEMETER_TIMEOUT = 600  # 10 minutos

        SONAR_HEAP_MB, SONAR_MIN_HEAP_MB = get_sonarqube_memory_limits(TOTAL_RAM_GB)

    else:  # 'auto'
        # Detección automática basada en RAM y CPUs
        workers = get_optimal_workers()
        MAX_PARALLEL_ANALYSIS = workers
        CELERY_WORKERS = workers
        ENABLE_PARALLEL = workers > 1
        USE_CELERY = workers > 1

        # Timeouts adaptativos
        if TOTAL_RAM_GB < 8:
            ANALYSIS_TIMEOUT = 900
            SONARQUBE_TIMEOUT = 600
            SOURCEMETER_TIMEOUT = 300
        else:
            ANALYSIS_TIMEOUT = 1200
            SONARQUBE_TIMEOUT = 900
            SOURCEMETER_TIMEOUT = 600

        SONAR_HEAP_MB, SONAR_MIN_HEAP_MB = get_sonarqube_memory_limits(TOTAL_RAM_GB)

    # ============================================
    # CONFIGURACIÓN AVANZADA DE CELERY
    # ============================================

    # Prefetch multiplier (cuántas tareas toma cada worker por adelantado)
    # Bajo = mejor distribución pero más overhead
    # Alto = menos overhead pero peor distribución
    CELERY_WORKER_PREFETCH_MULTIPLIER = 2 if ENABLE_PARALLEL else 1

    # Max tasks per child (reiniciar worker después de N tareas para evitar leaks)
    CELERY_WORKER_MAX_TASKS_PER_CHILD = 50

    # Task acks late (confirmar tarea DESPUÉS de completarla, más seguro)
    CELERY_TASK_ACKS_LATE = True

    # ============================================
    # LÍMITES DE SEGURIDAD
    # ============================================

    # Memoria mínima requerida (GB)
    MIN_REQUIRED_RAM_GB = 2

    # Validar recursos mínimos
    if TOTAL_RAM_GB < MIN_REQUIRED_RAM_GB:
        logger.warning(
            f"⚠️  RAM insuficiente: {TOTAL_RAM_GB:.1f}GB detectados, "
            f"se requieren al menos {MIN_REQUIRED_RAM_GB}GB"
        )

    @classmethod
    def get_config_summary(cls):
        """Retorna resumen de configuración actual"""
        return {
            # Entorno
            'mode': cls.MODE,
            'is_docker': cls.IS_DOCKER,
            'is_windows': cls.IS_WINDOWS,
            'is_linux': cls.IS_LINUX,

            # Recursos
            'total_ram_gb': round(cls.TOTAL_RAM_GB, 2),
            'available_ram_gb': round(cls.AVAILABLE_RAM_GB, 2),
            'cpu_count': cls.CPU_COUNT,
            'physical_cpu_count': cls.PHYSICAL_CPU_COUNT,

            # Configuración de análisis
            'max_parallel': cls.MAX_PARALLEL_ANALYSIS,
            'celery_workers': cls.CELERY_WORKERS,
            'parallel_enabled': cls.ENABLE_PARALLEL,
            'use_celery': cls.USE_CELERY,

            # Timeouts
            'analysis_timeout': cls.ANALYSIS_TIMEOUT,
            'sonarqube_timeout': cls.SONARQUBE_TIMEOUT,
            'sourcemeter_timeout': cls.SOURCEMETER_TIMEOUT,

            # SonarQube
            'sonar_heap_mb': cls.SONAR_HEAP_MB,
            'sonar_min_heap_mb': cls.SONAR_MIN_HEAP_MB,

            # Celery avanzado
            'celery_prefetch': cls.CELERY_WORKER_PREFETCH_MULTIPLIER,
            'celery_max_tasks': cls.CELERY_WORKER_MAX_TASKS_PER_CHILD,
        }

    @classmethod
    def log_config(cls):
        """Imprime configuración en los logs (formato mejorado)"""
        config = cls.get_config_summary()

        print("\n" + "=" * 70)
        print("🚀 NexSCAT - Configuración de Análisis")
        print("=" * 70)

        # Entorno
        print(f"\n📦 ENTORNO:")
        print(f"   Modo:             {config['mode'].upper()}")
        print(f"   Docker:           {'✅ Sí' if config['is_docker'] else '❌ No'}")
        print(f"   Sistema:          {'Windows' if config['is_windows'] else 'Linux' if config['is_linux'] else 'Mac'}")

        # Recursos
        print(f"\n💻 RECURSOS DEL SISTEMA:")
        print(f"   RAM Total:        {config['total_ram_gb']:.1f} GB")
        print(f"   RAM Disponible:   {config['available_ram_gb']:.1f} GB")
        print(f"   CPUs Lógicos:     {config['cpu_count']}")
        print(f"   CPUs Físicos:     {config['physical_cpu_count']}")

        # Configuración de análisis
        print(f"\n⚡ CONFIGURACIÓN DE ANÁLISIS:")
        print(f"   Análisis paralelos:  {config['max_parallel']}")
        print(f"   Workers Celery:      {config['celery_workers']}")
        print(f"   Paralelismo:         {'🟢 HABILITADO' if config['parallel_enabled'] else '🔴 DESHABILITADO'}")
        print(f"   Usar Celery:         {'✅ Sí' if config['use_celery'] else '❌ No (Secuencial)'}")

        # Timeouts
        print(f"\n⏱️  TIMEOUTS:")
        print(f"   Análisis total:   {config['analysis_timeout']}s ({config['analysis_timeout'] // 60}min)")
        print(f"   SonarQube:        {config['sonarqube_timeout']}s ({config['sonarqube_timeout'] // 60}min)")
        print(f"   SourceMeter:      {config['sourcemeter_timeout']}s ({config['sourcemeter_timeout'] // 60}min)")

        # SonarQube
        print(f"\n🔧 SONARQUBE:")
        print(f"   Heap máximo:      {config['sonar_heap_mb']} MB (-Xmx)")
        print(f"   Heap mínimo:      {config['sonar_min_heap_mb']} MB (-Xms)")

        # Celery avanzado
        if config['use_celery']:
            print(f"\n🐰 CELERY AVANZADO:")
            print(f"   Prefetch:         {config['celery_prefetch']}")
            print(f"   Max tasks/child:  {config['celery_max_tasks']}")

        print("\n" + "=" * 70 + "\n")

        # Advertencias
        if config['available_ram_gb'] < 2:
            print("⚠️  ADVERTENCIA: Poca RAM disponible, el rendimiento puede verse afectado")

        if config['use_celery'] and config['celery_workers'] > config['cpu_count']:
            print("⚠️  ADVERTENCIA: Más workers que CPUs, puede causar sobrecarga")

    @classmethod
    def get_docker_compose_env(cls):
        """
        Genera variables de entorno para docker-compose
        Útil para generar el archivo .env automáticamente
        """
        return {
            'SCAT_MODE': cls.MODE,
            'CELERY_WORKERS': cls.CELERY_WORKERS,
            'SONAR_CE_JAVAOPTS': f'-Xmx{cls.SONAR_HEAP_MB}m -Xms{cls.SONAR_MIN_HEAP_MB}m',
            'SONAR_WEB_JAVAOPTS': f'-Xmx{cls.SONAR_HEAP_MB}m -Xms{cls.SONAR_MIN_HEAP_MB}m',
        }


# ============================================
# EXPORTAR CONFIGURACIÓN
# ============================================
__all__ = ['AnalysisConfig']

# Log automático al importar (solo en debug)
if os.environ.get('DEBUG', 'False') == 'True':
    AnalysisConfig.log_config()