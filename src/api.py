"""
Optional REST API for GC-REDSS (Flask-based)
This is an optional component for future web interface integration
"""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

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
        fast_mode = data.get('fast_mode', True)  # Default to fast mode for better UX
        transport_modes = data.get('transport_modes', ['driving'])  # Default to driving only for speed
        
        if not work_address:
            return jsonify({"error": "work_address is required"}), 400
        
        logger.info(f"Scoring request: work_address={work_address}, fast_mode={fast_mode}")
        
        # Load processed data
        properties_df = processor.get_processed_data()
        
        # Use custom weights if provided
        if custom_weights:
            scoring_model.weights = custom_weights
            scoring_model._normalize_weights()
        
        # Score properties with fast mode enabled
        scored_df = scoring_model.score_properties(
            properties_df,
            work_address=work_address,
            commute_threshold_minutes=commute_threshold,
            life_threshold_minutes=life_threshold,
            transport_modes=transport_modes,
            fast_mode=fast_mode
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


@app.route('/api/geocode', methods=['POST'])
def geocode_address():
    """
    Geocode an address to get coordinates
    
    Request body:
    {
        "address": "Times Square, New York, NY"
    }
    """
    try:
        from src.geo_circle import GeoCircleCalculator
        
        data = request.get_json()
        address = data.get('address')
        
        if not address:
            return jsonify({"error": "address is required"}), 400
        
        calculator = GeoCircleCalculator()
        lat, lon = calculator.geocode_address(address)
        
        return jsonify({
            "status": "success",
            "address": address,
            "latitude": lat,
            "longitude": lon
        })
        
    except Exception as e:
        logger.error(f"Error geocoding address: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


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
    import os
    import socket
    
    logging.basicConfig(level=logging.INFO)
    init_spark()
    
    # Function to check if port is available
    def is_port_available(port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('localhost', port))
                return True
            except OSError:
                return False
    
    # Try to find an available port (try 5000, 5001, 5002, 5003, 5004)
    preferred_port = int(os.environ.get('FLASK_PORT', 5000))
    port = None
    
    for test_port in [preferred_port, 5001, 5002, 5003, 5004, 5005]:
        if is_port_available(test_port):
            port = test_port
            if test_port != preferred_port:
                logger.warning(f"Port {preferred_port} is in use, using port {port} instead")
            break
    
    if port is None:
        logger.error("Could not find an available port (tried 5000-5005).")
        logger.error("Please free up a port or set FLASK_PORT environment variable.")
        logger.error("On macOS, you can disable AirPlay Receiver in System Settings.")
        sys.exit(1)
    
    logger.info("=" * 80)
    logger.info(f"🚀 Starting Flask API server on port {port}")
    logger.info(f"📡 API will be available at: http://localhost:{port}")
    logger.info(f"❤️  Health check: http://localhost:{port}/health")
    logger.info(f"🔍 Score endpoint: http://localhost:{port}/api/score")
    logger.info("=" * 80)
    logger.info(f"💡 Note: Update frontend config if using a different port")
    logger.info("=" * 80)
    
    app.run(host='0.0.0.0', port=port, debug=True)
