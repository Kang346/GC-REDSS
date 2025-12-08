"""
Configuration settings for GC-REDSS
"""
import os
from pathlib import Path

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# Data paths
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
OUTPUT_DIR = PROJECT_ROOT / "output"

# Create directories if they don't exist
for dir_path in [DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, OUTPUT_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# Spark configuration
SPARK_CONFIG = {
    "spark.app.name": "GC-REDSS",
    "spark.master": "local[*]",
    "spark.sql.warehouse.dir": str(PROJECT_ROOT / "spark-warehouse"),
    "spark.driver.memory": "4g",
    "spark.executor.memory": "4g",
    "spark.sql.execution.arrow.pyspark.enabled": "true",
}

# Geo-Circle default settings
DEFAULT_COMMUTE_THRESHOLD = 30  # minutes
DEFAULT_LIFE_THRESHOLD = 15  # minutes
DEFAULT_TRANSPORT_MODES = ["driving", "walking", "transit"]

# Scoring model default weights
DEFAULT_SCORING_WEIGHTS = {
    "price": 0.3,
    "commute_time": 0.25,
    "life_accessibility": 0.15,
    "property_size": 0.1,
    "bedrooms": 0.1,
    "bathrooms": 0.1,
}

# OSMnx settings
OSMNX_SETTINGS = {
    "network_type": "all",  # 'drive', 'walk', 'bike', 'all'
    "timeout": 180,
    "memory": None,
    "max_query_area_size": 50 * 1000 * 50 * 1000,  # 50km x 50km
}
