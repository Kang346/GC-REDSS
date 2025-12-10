"""
Main application entry point for GC-REDSS
"""
import logging
import argparse
import sys
from pathlib import Path
from pyspark.sql import SparkSession
from pyspark.sql.functions import col

# Add project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.config import (
    RAW_DATA_DIR, PROCESSED_DATA_DIR, OUTPUT_DIR,
    SPARK_CONFIG, DEFAULT_COMMUTE_THRESHOLD, DEFAULT_LIFE_THRESHOLD,
    DEFAULT_TRANSPORT_MODES, DEFAULT_SCORING_WEIGHTS
)
from src.data_processor import DataProcessor
from src.scoring_model import ScoringModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main application function"""
    parser = argparse.ArgumentParser(
        description="Geo-Circle Based Real Estate Decision Support System"
    )
    parser.add_argument(
        "--work-address",
        type=str,
        required=True,
        help="Address of workplace (e.g., 'Times Square, New York, NY')"
    )
    parser.add_argument(
        "--commute-threshold",
        type=float,
        default=DEFAULT_COMMUTE_THRESHOLD,
        help=f"Maximum commute time in minutes (default: {DEFAULT_COMMUTE_THRESHOLD})"
    )
    parser.add_argument(
        "--life-threshold",
        type=float,
        default=DEFAULT_LIFE_THRESHOLD,
        help=f"Maximum walking time to amenities in minutes (default: {DEFAULT_LIFE_THRESHOLD})"
    )
    parser.add_argument(
        "--input-file",
        type=str,
        default=None,
        help="Path to input CSV file (default: data/raw/NY-House-Dataset.csv)"
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default=None,
        help="Path to output file (default: output/scored_properties.parquet)"
    )
    parser.add_argument(
        "--skip-processing",
        action="store_true",
        help="Skip data processing and use existing processed data"
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="Number of top properties to display (default: 20)"
    )
    
    args = parser.parse_args()
    
    # Initialize Spark
    spark = SparkSession.builder \
        .appName(SPARK_CONFIG["spark.app.name"]) \
        .config("spark.sql.warehouse.dir", SPARK_CONFIG["spark.sql.warehouse.dir"]) \
        .config("spark.driver.memory", SPARK_CONFIG["spark.driver.memory"]) \
        .config("spark.executor.memory", SPARK_CONFIG["spark.executor.memory"]) \
        .config("spark.sql.execution.arrow.pyspark.enabled", 
               SPARK_CONFIG["spark.sql.execution.arrow.pyspark.enabled"]) \
        .getOrCreate()
    
    try:
        # Step 1: Data Processing
        processor = DataProcessor(spark)
        
        if args.skip_processing:
            logger.info("Loading existing processed data...")
            properties_df = processor.get_processed_data()
        else:
            logger.info("Processing raw data...")
            properties_df = processor.process(input_path=args.input_file)
        
        logger.info(f"Total properties: {properties_df.count()}")
        
        # Step 2: Scoring
        logger.info("Calculating property scores...")
        scoring_model = ScoringModel(weights=DEFAULT_SCORING_WEIGHTS)
        
        scored_df = scoring_model.score_properties(
            properties_df,
            work_address=args.work_address,
            commute_threshold_minutes=args.commute_threshold,
            life_threshold_minutes=args.life_threshold,
            transport_modes=DEFAULT_TRANSPORT_MODES
        )
        
        # Step 3: Save results
        if args.output_file is None:
            output_file = str(OUTPUT_DIR / "scored_properties.parquet")
        else:
            output_file = args.output_file
        
        logger.info(f"Saving scored properties to {output_file}")
        scored_df.write.mode("overwrite").parquet(output_file)
        
        # Step 4: Display top properties
        logger.info(f"\n{'='*80}")
        logger.info(f"Top {args.top_n} Properties by S Score:")
        logger.info(f"{'='*80}\n")
        
        top_properties = scored_df.orderBy(col("SCORE_S_SCORE").desc()).limit(args.top_n)
        top_properties_pd = top_properties.toPandas()
        
        # Display key information
        display_cols = [
            "ADDRESS", "PRICE", "BEDS", "BATH", "PROPERTYSQFT",
            "SCORE_S_SCORE", "SCORE_COMMUTE_SCORE", "SCORE_LIFE_SCORE", "SCORE_PRICE_SCORE"
        ]
        available_cols = [col for col in display_cols if col in top_properties_pd.columns]
        
        print(top_properties_pd[available_cols].to_string(index=False))
        
        # Save top properties as CSV for easy viewing
        csv_output = str(OUTPUT_DIR / "top_properties.csv")
        top_properties_pd.to_csv(csv_output, index=False)
        logger.info(f"\nTop properties saved to {csv_output}")
        
        logger.info("\nProcessing completed successfully!")
        
    except Exception as e:
        logger.error(f"Error in main processing: {e}", exc_info=True)
        raise
    
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
