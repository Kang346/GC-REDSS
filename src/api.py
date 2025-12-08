"""
Optional REST API for GC-REDSS (Flask-based)
This is an optional component for future web interface integration
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
from pyspark.sql import SparkSession
import logging

from src.config import SPARK_CONFIG, DEFAULT_SCORING_WEIGHTS
from src.data_processor import DataProcessor
from src.scoring_model import ScoringModel

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend integration

logger = logging.getLogger(__name__)

# Global Spark session (initialize once)
spark = None
processor = None
scoring_model = None


def init_spark():
    """Initialize Spark session and models"""
    global spark, processor, scoring_model
    
    if spark is None:
        spark = SparkSession.builder \
            .appName(SPARK_CONFIG["spark.app.name"]) \
            .config("spark.sql.warehouse.dir", SPARK_CONFIG["spark.sql.warehouse.dir"]) \
            .getOrCreate()
        
        processor = DataProcessor(spark)
        scoring_model = ScoringModel(weights=DEFAULT_SCORING_WEIGHTS)
        
        logger.info("Spark session and models initialized")


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "GC-REDSS"})


@app.route('/api/score', methods=['POST'])
def score_properties():
    """
    Score properties based on user criteria
    
    Request body:
    {
        "work_address": "Times Square, New York, NY",
        "commute_threshold": 30,
        "life_threshold": 15,
        "top_n": 20,
        "weights": {
            "price": 0.3,
            "commute_time": 0.25,
            ...
        }
    }
    """
    try:
        init_spark()
        
        data = request.get_json()
        
        work_address = data.get('work_address')
        commute_threshold = data.get('commute_threshold', 30)
        life_threshold = data.get('life_threshold', 15)
        top_n = data.get('top_n', 20)
        custom_weights = data.get('weights')
        
        if not work_address:
            return jsonify({"error": "work_address is required"}), 400
        
        # Load processed data
        properties_df = processor.get_processed_data()
        
        # Use custom weights if provided
        if custom_weights:
            scoring_model.weights = custom_weights
            scoring_model._normalize_weights()
        
        # Score properties
        scored_df = scoring_model.score_properties(
            properties_df,
            work_address=work_address,
            commute_threshold_minutes=commute_threshold,
            life_threshold_minutes=life_threshold
        )
        
        # Get top N properties
        from pyspark.sql.functions import col
        top_properties = scored_df.orderBy(col("SCORE_S_SCORE").desc()).limit(top_n)
        top_properties_pd = top_properties.toPandas()
        
        # Convert to JSON-serializable format
        results = top_properties_pd.to_dict('records')
        
        return jsonify({
            "status": "success",
            "count": len(results),
            "properties": results
        })
        
    except Exception as e:
        logger.error(f"Error in score_properties: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    return jsonify({
        "default_weights": DEFAULT_SCORING_WEIGHTS,
        "spark_config": {
            "driver_memory": SPARK_CONFIG.get("spark.driver.memory"),
            "executor_memory": SPARK_CONFIG.get("spark.executor.memory"),
        }
    })


@app.route('/api/config/weights', methods=['POST'])
def update_weights():
    """
    Update scoring weights
    
    Request body:
    {
        "weights": {
            "price": 0.3,
            "commute_time": 0.25,
            ...
        }
    }
    """
    try:
        global scoring_model
        init_spark()
        
        data = request.get_json()
        new_weights = data.get('weights')
        
        if not new_weights:
            return jsonify({"error": "weights are required"}), 400
        
        scoring_model.weights = new_weights
        scoring_model._normalize_weights()
        
        return jsonify({
            "status": "success",
            "weights": scoring_model.weights
        })
        
    except Exception as e:
        logger.error(f"Error updating weights: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    init_spark()
    app.run(host='0.0.0.0', port=5000, debug=True)
