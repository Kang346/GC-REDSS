"""
Example usage of GC-REDSS system
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from pyspark.sql import SparkSession
from src.data_processor import DataProcessor
from src.scoring_model import ScoringModel
from src.config import (
    SPARK_CONFIG, DEFAULT_COMMUTE_THRESHOLD, DEFAULT_LIFE_THRESHOLD,
    DEFAULT_TRANSPORT_MODES, DEFAULT_SCORING_WEIGHTS
)

# Initialize Spark
spark = SparkSession.builder \
    .appName("GC-REDSS-Example") \
    .config("spark.sql.warehouse.dir", SPARK_CONFIG["spark.sql.warehouse.dir"]) \
    .config("spark.driver.memory", "2g") \
    .config("spark.executor.memory", "2g") \
    .getOrCreate()

try:
    print("=" * 80)
    print("GC-REDSS Example Usage")
    print("=" * 80)
    
    # Step 1: Process data
    print("\n[Step 1] Processing raw data...")
    processor = DataProcessor(spark)
    properties_df = processor.process()
    print(f"Processed {properties_df.count()} properties")
    
    # Step 2: Score properties
    print("\n[Step 2] Calculating property scores...")
    print("Work address: Times Square, New York, NY")
    print(f"Commute threshold: {DEFAULT_COMMUTE_THRESHOLD} minutes")
    print(f"Life threshold: {DEFAULT_LIFE_THRESHOLD} minutes")
    
    scoring_model = ScoringModel(weights=DEFAULT_SCORING_WEIGHTS)
    
    scored_df = scoring_model.score_properties(
        properties_df,
        work_address="Times Square, New York, NY",
        commute_threshold_minutes=DEFAULT_COMMUTE_THRESHOLD,
        life_threshold_minutes=DEFAULT_LIFE_THRESHOLD,
        transport_modes=DEFAULT_TRANSPORT_MODES
    )
    
    # Step 3: Display results
    print("\n[Step 3] Top 10 properties by S Score:")
    print("-" * 80)
    
    from pyspark.sql.functions import col
    top_10 = scored_df.orderBy(col("SCORE_S_SCORE").desc()).limit(10)
    top_10_pd = top_10.select(
        "ADDRESS", "PRICE", "BEDS", "BATH", "PROPERTYSQFT", "SCORE_S_SCORE"
    ).toPandas()
    
    print(top_10_pd.to_string(index=False))
    
    print("\n" + "=" * 80)
    print("Example completed successfully!")
    print("=" * 80)
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    
finally:
    spark.stop()
