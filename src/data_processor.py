"""
Data processing module using PySpark for cleaning and feature engineering
"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, when, isnan, isnull, trim, lower, regexp_replace,
    udf, round as spark_round
)
from pyspark.sql.types import DoubleType, IntegerType, StringType
import logging
from pathlib import Path

from src.config import RAW_DATA_DIR, PROCESSED_DATA_DIR, SPARK_CONFIG

logger = logging.getLogger(__name__)


class DataProcessor:
    """Process real estate data using PySpark"""
    
    def __init__(self, spark_session: SparkSession = None):
        """
        Initialize DataProcessor
        
        Args:
            spark_session: Optional SparkSession. If None, creates a new one.
        """
        if spark_session is None:
            self.spark = SparkSession.builder \
                .appName(SPARK_CONFIG["spark.app.name"]) \
                .config("spark.sql.warehouse.dir", SPARK_CONFIG["spark.sql.warehouse.dir"]) \
                .config("spark.driver.memory", SPARK_CONFIG["spark.driver.memory"]) \
                .config("spark.executor.memory", SPARK_CONFIG["spark.executor.memory"]) \
                .config("spark.sql.execution.arrow.pyspark.enabled", 
                       SPARK_CONFIG["spark.sql.execution.arrow.pyspark.enabled"]) \
                .getOrCreate()
        else:
            self.spark = spark_session
        
        logger.info("DataProcessor initialized")
    
    def load_raw_data(self, file_path: str = None, auto_download: bool = False) -> 'DataFrame':
        """
        Load raw CSV data
        
        Args:
            file_path: Path to CSV file. If None, uses default path.
            auto_download: If True and file doesn't exist, attempt to download from Kaggle.
            
        Returns:
            Spark DataFrame with raw data
        """
        if file_path is None:
            file_path = str(RAW_DATA_DIR / "NY-House-Dataset.csv")
        
        # Check if file exists, optionally download if missing
        if not Path(file_path).exists():
            if auto_download:
                logger.info(f"Data file not found at {file_path}. Attempting to download...")
                try:
                    import importlib.util
                    project_root = Path(__file__).parent.parent
                    download_script = project_root / "scripts" / "download_data.py"
                    spec = importlib.util.spec_from_file_location("download_data", download_script)
                    download_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(download_module)
                    file_path = download_module.download_kaggle_dataset()
                except Exception as e:
                    logger.error(f"Auto-download failed: {e}")
                    logger.error("Please run: python scripts/download_data.py")
                    raise FileNotFoundError(
                        f"Data file not found at {file_path}. "
                        "Run 'python scripts/download_data.py' to download the dataset."
                    )
            else:
                raise FileNotFoundError(
                    f"Data file not found at {file_path}. "
                    "Run 'python scripts/download_data.py' to download the dataset, "
                    "or set auto_download=True to download automatically."
                )
        
        logger.info(f"Loading data from {file_path}")
        df = self.spark.read.csv(
            file_path,
            header=True,
            inferSchema=True,
            nullValue="",
            nanValue=""
        )
        
        logger.info(f"Loaded {df.count()} records")
        return df
    
    def clean_data(self, df) -> 'DataFrame':
        """
        Clean and standardize the dataset
        
        Args:
            df: Input Spark DataFrame
            
        Returns:
            Cleaned Spark DataFrame
        """
        logger.info("Starting data cleaning...")
        
        # Remove duplicates
        initial_count = df.count()
        df = df.dropDuplicates()
        logger.info(f"Removed {initial_count - df.count()} duplicate records")
        
        # Clean and standardize columns
        df = df.withColumn("PRICE", 
            when(col("PRICE").isNull() | (col("PRICE") <= 0), None)
            .otherwise(col("PRICE")))
        
        df = df.withColumn("BEDS",
            when(col("BEDS").isNull() | (col("BEDS") < 0), None)
            .otherwise(col("BEDS").cast(IntegerType())))
        
        df = df.withColumn("BATH",
            when(col("BATH").isNull() | (col("BATH") < 0), None)
            .otherwise(col("BATH").cast(DoubleType())))
        
        df = df.withColumn("PROPERTYSQFT",
            when(col("PROPERTYSQFT").isNull() | (col("PROPERTYSQFT") <= 0), None)
            .otherwise(col("PROPERTYSQFT").cast(DoubleType())))
        
        # Clean address fields
        df = df.withColumn("ADDRESS", trim(col("ADDRESS")))
        df = df.withColumn("FORMATTED_ADDRESS", trim(col("FORMATTED_ADDRESS")))
        
        # Ensure latitude and longitude are valid
        df = df.withColumn("LATITUDE",
            when((col("LATITUDE").isNull()) | 
                 (col("LATITUDE") < -90) | (col("LATITUDE") > 90), None)
            .otherwise(col("LATITUDE").cast(DoubleType())))
        
        df = df.withColumn("LONGITUDE",
            when((col("LONGITUDE").isNull()) | 
                 (col("LONGITUDE") < -180) | (col("LONGITUDE") > 180), None)
            .otherwise(col("LONGITUDE").cast(DoubleType())))
        
        # Filter out records without essential geospatial data
        df = df.filter(
            col("LATITUDE").isNotNull() & 
            col("LONGITUDE").isNotNull() &
            col("PRICE").isNotNull()
        )
        
        logger.info(f"After cleaning: {df.count()} records remain")
        return df
    
    def engineer_features(self, df) -> 'DataFrame':
        """
        Create derived features for scoring model
        
        Args:
            df: Input Spark DataFrame
            
        Returns:
            DataFrame with additional features
        """
        logger.info("Engineering features...")
        
        # Calculate price per square foot
        df = df.withColumn(
            "PRICE_PER_SQFT",
            when(col("PROPERTYSQFT").isNotNull() & (col("PROPERTYSQFT") > 0),
                 col("PRICE") / col("PROPERTYSQFT"))
            .otherwise(None)
        )
        
        # Calculate bedrooms per bathroom ratio
        df = df.withColumn(
            "BEDS_PER_BATH",
            when(col("BATH").isNotNull() & (col("BATH") > 0),
                 col("BEDS") / col("BATH"))
            .otherwise(None)
        )
        
        # Create property type category
        df = df.withColumn(
            "PROPERTY_TYPE_CLEAN",
            lower(regexp_replace(col("TYPE"), r"\s+", "_"))
        )
        
        # Extract borough from administrative area
        df = df.withColumn(
            "BOROUGH",
            when(col("ADMINISTRATIVE_AREA_LEVEL_2").contains("Manhattan"), "Manhattan")
            .when(col("ADMINISTRATIVE_AREA_LEVEL_2").contains("Kings"), "Brooklyn")
            .when(col("ADMINISTRATIVE_AREA_LEVEL_2").contains("Queens"), "Queens")
            .when(col("ADMINISTRATIVE_AREA_LEVEL_2").contains("Richmond"), "Staten Island")
            .when(col("ADMINISTRATIVE_AREA_LEVEL_2").contains("Bronx"), "Bronx")
            .otherwise(col("ADMINISTRATIVE_AREA_LEVEL_2"))
        )
        
        logger.info("Feature engineering completed")
        return df
    
    def process(self, input_path: str = None, output_path: str = None) -> 'DataFrame':
        """
        Complete data processing pipeline
        
        Args:
            input_path: Path to input CSV file
            output_path: Path to save processed data (Parquet format)
            
        Returns:
            Processed Spark DataFrame
        """
        # Load data
        df = self.load_raw_data(input_path)
        
        # Clean data
        df = self.clean_data(df)
        
        # Engineer features
        df = self.engineer_features(df)
        
        # Save processed data
        if output_path is None:
            output_path = str(PROCESSED_DATA_DIR / "processed_houses.parquet")
        
        logger.info(f"Saving processed data to {output_path}")
        df.write.mode("overwrite").parquet(output_path)
        
        logger.info("Data processing completed successfully")
        return df
    
    def get_processed_data(self, file_path: str = None) -> 'DataFrame':
        """
        Load previously processed data
        
        Args:
            file_path: Path to processed Parquet file
            
        Returns:
            Spark DataFrame with processed data
        """
        if file_path is None:
            file_path = str(PROCESSED_DATA_DIR / "processed_houses.parquet")
        
        logger.info(f"Loading processed data from {file_path}")
        df = self.spark.read.parquet(file_path)
        return df
