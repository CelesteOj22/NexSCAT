# scat/config.py
"""
Configuración adaptativa según recursos del sistema
"""
import os
import psutil
import logging

logger = logging.getLogger(__name__)


def get_system_ram_gb():
    """Obtiene RAM total del sistema en GB"""
    try:
        return psutil.virtual_memory().total / (1024 ** 3)
    except Exception as e:
        logger.warning(f"No se pudo detectar RAM: {e}")
        return 4  # Default conservador


def get_optimal_workers():
    """
    Determina automáticamente cuántos workers usar
    basándose en RAM disponible
    """
    total_ram_gb = get_system_ram_gb()

    if total_ram_gb < 4:
        return 1  # Muy poca RAM
    elif total_ram_gb < 8:
        return 1  # AWS t3.medium - Secuencial
    elif total_ram_gb < 12:
        return 2  # AWS t3.large - Poco paralelo
    elif total_ram_gb < 16:
        return 4  # Desarrollo
    elif total_ram_gb < 32:
        return 6  # Local potente
    else:
        return 8  # Workstation


class AnalysisConfig:
    """Configuración de análisis según entorno"""

    # Modo de operación (se puede override con env var)
    MODE = os.environ.get('SCAT_MODE', 'auto')

    if MODE == 'production':
        # AWS - Recursos limitados - Análisis secuencial
        MAX_PARALLEL_ANALYSIS = 1
        CELERY_WORKERS = 1
        ENABLE_PARALLEL = False
        ANALYSIS_TIMEOUT = 600
        USE_CELERY = False  # Sin Celery en producción simple

    elif MODE == 'development':
        # Local - Desarrollo con recursos moderados
        MAX_PARALLEL_ANALYSIS = 2
        CELERY_WORKERS = 2
        ENABLE_PARALLEL = True
        ANALYSIS_TIMEOUT = 1200
        USE_CELERY = True

    elif MODE == 'performance':
        # Local - Máximo rendimiento
        workers = get_optimal_workers()
        MAX_PARALLEL_ANALYSIS = workers
        CELERY_WORKERS = workers
        ENABLE_PARALLEL = True
        ANALYSIS_TIMEOUT = 1800
        USE_CELERY = True

    else:  # 'auto'
        # Detección automática basada en RAM
        workers = get_optimal_workers()
        MAX_PARALLEL_ANALYSIS = workers
        CELERY_WORKERS = workers
        ENABLE_PARALLEL = workers > 1
        ANALYSIS_TIMEOUT = 1200
        USE_CELERY = workers > 1

    @classmethod
    def get_config_summary(cls):
        """Retorna resumen de configuración actual"""
        ram_gb = get_system_ram_gb()
        return {
            'mode': cls.MODE,
            'max_parallel': cls.MAX_PARALLEL_ANALYSIS,
            'celery_workers': cls.CELERY_WORKERS,
            'parallel_enabled': cls.ENABLE_PARALLEL,
            'use_celery': cls.USE_CELERY,
            'timeout': cls.ANALYSIS_TIMEOUT,
            'total_ram_gb': round(ram_gb, 2),
            'available_ram_gb': round(psutil.virtual_memory().available / (1024 ** 3), 2),
        }

    @classmethod
    def log_config(cls):
        """Imprime configuración en los logs"""
        config = cls.get_config_summary()
        logger.info("=" * 60)
        logger.info("SCAT - Configuración de Análisis")
        logger.info("=" * 60)
        logger.info(f"Modo: {config['mode']}")
        logger.info(f"RAM Total: {config['total_ram_gb']} GB")
        logger.info(f"RAM Disponible: {config['available_ram_gb']} GB")
        logger.info(f"Análisis paralelos máx: {config['max_parallel']}")
        logger.info(f"Workers Celery: {config['celery_workers']}")
        logger.info(f"Paralelismo habilitado: {config['parallel_enabled']}")
        logger.info(f"Usar Celery: {config['use_celery']}")
        logger.info(f"Timeout: {config['timeout']}s")
        logger.info("=" * 60)