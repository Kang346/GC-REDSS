"""
Example usage of GC-REDSS system
"""
import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging to show INFO level messages
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

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
    print(f"Transport modes: {', '.join(DEFAULT_TRANSPORT_MODES)}")
    print("\n" + "⚠️  IMPORTANT: This step will download road network data from OpenStreetMap")
    print("   - First run may take 3-5 minutes (downloading network data)")
    print("   - Subsequent runs will be faster (using cached data)")
    print("   - Please be patient, downloading in progress...")
    print("-" * 80)
    
    scoring_model = ScoringModel(weights=DEFAULT_SCORING_WEIGHTS)
    
    print("\n🔄 Starting score calculation...")
    print("   Step 2.1: Downloading road network data (this may take 1-3 minutes)...")
    print("   Step 2.2: Calculating commute circles for each transport mode...")
    print("   Step 2.3: Calculating property scores...")
    print()
    print("📡 Now downloading road network data - please wait...")
    print("   (You'll see detailed progress messages below)")
    print("-" * 80)
    
    scored_df = scoring_model.score_properties(
        properties_df,
        work_address="Times Square, New York, NY",
        commute_threshold_minutes=DEFAULT_COMMUTE_THRESHOLD,
        life_threshold_minutes=DEFAULT_LIFE_THRESHOLD,
        transport_modes=DEFAULT_TRANSPORT_MODES
    )
    
    print("\n✅ Score calculation completed!")
    
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
