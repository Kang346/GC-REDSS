# Geo-Circle Based Interpretable Real Estate Decision Support System (GC-REDSS)

## Overview

GC-REDSS is a Big Data-driven decision support system for real estate selection that addresses the rigid limitations of traditional search filters. Instead of hard thresholds, the system uses:

- **Static Isochrone Analysis (Geo-Circles)**: Calculated from OpenStreetMap data to define flexible "Commute" and "Life" accessibility zones
- **Elastic Filtering**: A transparent, weighted scoring model that provides adjustable S scores, allowing users to evaluate properties even if they fall just outside defined circles
- **Multi-modal Transport Analysis**: Supports driving, walking, and transit modes

## Features

- **Data Processing**: PySpark-based data cleaning and feature engineering
- **Geo-Spatial Analysis**: Isochrone calculation using OSMnx and NetworkX
- **Elastic Scoring Model**: Weighted scoring system with configurable weights
- **Multi-transport Mode Support**: Calculate commute circles for different transport modes
- **Docker Support**: Easy deployment with Docker and Docker Compose
- **REST API**: Optional Flask-based API for web integration

## Project Structure

```
.
├── src/
│   ├── __init__.py
│   ├── config.py              # Configuration settings
│   ├── data_processor.py      # PySpark data processing
│   ├── geo_circle.py          # Isochrone calculation
│   ├── scoring_model.py       # Elastic filtering scoring
│   ├── main.py                # Main application entry point
│   ├── api.py                 # Optional REST API (Flask)
│   └── utils.py               # Utility functions
├── examples/
│   └── example_usage.py       # Example usage script
├── data/
│   ├── raw/                   # Raw CSV data
│   └── processed/             # Processed Parquet files
├── output/                    # Output files (scored properties)
├── requirements.txt           # Python dependencies
├── Dockerfile                 # Docker configuration
├── docker-compose.yml         # Docker Compose configuration
├── README.md                  # This file
└── README_CN.md               # Chinese documentation
```

## System Workflow

The GC-REDSS system follows a three-stage pipeline:

```
┌─────────────────────────────────────────────────────────────┐
│                      INPUT DATA                             │
│  CSV File: NY-House-Dataset.csv                            │
│  - Property addresses, prices, bedrooms, bathrooms, etc.    │
│  - Latitude and longitude coordinates                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│          STAGE 1: DATA PROCESSING                           │
│  DataProcessor Module                                       │
│  ├─ Load raw CSV data                                       │
│  ├─ Data cleaning (remove duplicates, validate coordinates) │
│  ├─ Feature engineering (price/sqft, beds/bath ratio, etc.) │
│  └─ Output: Cleaned Spark DataFrame + Parquet file        │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│          STAGE 2: GEO-CIRCLE CALCULATION                    │
│  GeoCircleCalculator Module                                 │
│  ├─ Geocode work address → coordinates                      │
│  ├─ Download road network from OpenStreetMap                │
│  ├─ Calculate isochrones for commute (driving/walk/transit) │
│  ├─ Calculate isochrones for life accessibility (walking)  │
│  └─ Output: Polygon objects for each circle                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│          STAGE 3: SCORING & RANKING                         │
│  ScoringModel Module                                        │
│  ├─ Calculate individual feature scores                    │
│  │  • Price score (normalized, lower is better)            │
│  │  • Commute score (based on geo-circles)                  │
│  │  • Life accessibility score                             │
│  │  • Property size, bedrooms, bathrooms scores            │
│  ├─ Apply elastic filtering (exponential decay outside)     │
│  ├─ Weighted combination → S Score                          │
│  └─ Output: Scored DataFrame + Top N CSV                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                      OUTPUT RESULTS                         │
│  • scored_properties.parquet (full dataset with scores)    │
│  • top_properties.csv (Top N properties)                   │
│  • Console output (ranked list)                             │
└─────────────────────────────────────────────────────────────┘
```

### Detailed Workflow Steps

1. **Data Loading & Cleaning**
   - Load CSV file into Spark DataFrame
   - Remove duplicate records
   - Validate and clean coordinates (latitude: -90 to 90, longitude: -180 to 180)
   - Filter out records with missing essential data (price, coordinates)
   - Standardize address fields

2. **Feature Engineering**
   - Calculate `PRICE_PER_SQFT` (price / square footage)
   - Calculate `BEDS_PER_BATH` ratio
   - Extract `BOROUGH` from administrative area
   - Normalize property types

3. **Geo-Circle Calculation**
   - Convert work address to coordinates using Geopy
   - Download road network from OpenStreetMap (cached for performance)
   - Calculate shortest path times from work location to all reachable nodes
   - Generate isochrone polygons for each transport mode
   - Create life accessibility circle (walking distance to amenities)

4. **Scoring & Ranking**
   - For each property:
     - Check if inside/outside each geo-circle
     - Calculate distance to circle boundary if outside
     - Apply elastic filtering (exponential decay: `exp(-penalty * 2)`)
     - Normalize all features to [0, 1] range
     - Calculate weighted S Score
   - Sort by S Score and return Top N

## Installation

### Using Docker (Recommended)

1. **Build and start the container:**
   ```bash
   docker-compose up --build
   ```

2. **Access JupyterLab:**
   - Open your browser and navigate to `http://localhost:8888`
   - The project files will be available in the workspace

3. **Stop the container:**
   ```bash
   docker-compose down
   ```

### Local Installation

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Ensure you have Java installed** (required for PySpark):
   - Java 8 or higher
   - Verify: `java -version`

3. **Set up data directory:**
   - Place your CSV file in `data/raw/NY-House-Dataset.csv`

## Usage

### Method 1: Command Line Interface (CLI)

**Basic usage:**
```bash
python src/main.py \
    --work-address "Times Square, New York, NY" \
    --commute-threshold 30 \
    --life-threshold 15 \
    --top-n 20
```

**With custom input/output:**
```bash
python src/main.py \
    --work-address "Central Park, New York, NY" \
    --commute-threshold 45 \
    --input-file "data/raw/custom_data.csv" \
    --output-file "output/my_results.parquet" \
    --top-n 50
```

**Skip data processing (use existing processed data):**
```bash
python src/main.py \
    --work-address "Brooklyn Bridge, New York, NY" \
    --skip-processing \
    --commute-threshold 30
```

**In Docker container:**
```bash
# Set PYTHONPATH first
cd /home/jovyan/work
export PYTHONPATH=/home/jovyan/work:$PYTHONPATH

# Or use module syntax
python -m src.main \
    --work-address "Times Square, New York, NY" \
    --commute-threshold 30 \
    --life-threshold 15 \
    --top-n 20
```

**Command-line Arguments:**

| Argument              | Type  | Required | Default                            | Description                                 |
| --------------------- | ----- | -------- | ---------------------------------- | ------------------------------------------- |
| `--work-address`      | str   | ✅        | -                                  | Address of workplace                        |
| `--commute-threshold` | float | ❌        | 30                                 | Maximum commute time (minutes)              |
| `--life-threshold`    | float | ❌        | 15                                 | Maximum walking time to amenities (minutes) |
| `--input-file`        | str   | ❌        | `data/raw/NY-House-Dataset.csv`    | Input CSV file path                         |
| `--output-file`       | str   | ❌        | `output/scored_properties.parquet` | Output file path                            |
| `--skip-processing`   | flag  | ❌        | False                              | Skip data processing, use existing data     |
| `--top-n`             | int   | ❌        | 20                                 | Number of top properties to display         |

### Method 2: Python API (Programmatic)

**Basic usage:**
```python
from pyspark.sql import SparkSession
from src.data_processor import DataProcessor
from src.scoring_model import ScoringModel

# Initialize Spark
spark = SparkSession.builder.appName("GC-REDSS").getOrCreate()

# Step 1: Process data
processor = DataProcessor(spark)
properties_df = processor.process()

# Step 2: Score properties
scoring_model = ScoringModel()
scored_df = scoring_model.score_properties(
    properties_df,
    work_address="Times Square, New York, NY",
    commute_threshold_minutes=30,
    life_threshold_minutes=15
)

# Step 3: Get top properties
from pyspark.sql.functions import col
top_10 = scored_df.orderBy(col("SCORE_S_SCORE").desc()).limit(10)
top_10.show()
```

**With custom weights:**
```python
from src.scoring_model import ScoringModel

# Define custom weights
custom_weights = {
    "price": 0.4,              # More emphasis on price
    "commute_time": 0.3,       # More emphasis on commute
    "life_accessibility": 0.1,
    "property_size": 0.1,
    "bedrooms": 0.05,
    "bathrooms": 0.05,
}

# Use custom weights
scoring_model = ScoringModel(weights=custom_weights)
scored_df = scoring_model.score_properties(
    properties_df,
    work_address="Times Square, New York, NY",
    commute_threshold_minutes=30
)
```

### Method 3: Jupyter Notebook

1. **Start Docker container:**
   ```bash
   docker-compose up
   ```

2. **Open JupyterLab:** `http://localhost:8888`

3. **Create new notebook** and run:
   ```python
   import sys
   from pathlib import Path
   sys.path.insert(0, str(Path.cwd()))
   
   from pyspark.sql import SparkSession
   from src.data_processor import DataProcessor
   from src.scoring_model import ScoringModel
   
   # Your code here...
   ```

### Method 4: REST API

**Start the API server:**
```bash
python src/api.py
```

The API will be available at `http://localhost:5000`

**API Endpoints:**

1. **Health Check**
   ```bash
   GET http://localhost:5000/health
   ```
   Response:
   ```json
   {
     "status": "healthy",
     "service": "GC-REDSS"
   }
   ```

2. **Score Properties**
   ```bash
   POST http://localhost:5000/api/score
   Content-Type: application/json
   
   {
     "work_address": "Times Square, New York, NY",
     "commute_threshold": 30,
     "life_threshold": 15,
     "top_n": 20,
     "weights": {
       "price": 0.3,
       "commute_time": 0.25,
       "life_accessibility": 0.15,
       "property_size": 0.1,
       "bedrooms": 0.1,
       "bathrooms": 0.1
     }
   }
   ```
   Response:
   ```json
   {
     "status": "success",
     "count": 20,
     "properties": [
       {
         "ADDRESS": "...",
         "PRICE": 315000,
         "SCORE_S_SCORE": 0.85,
         ...
       },
       ...
     ]
   }
   ```

3. **Get Configuration**
   ```bash
   GET http://localhost:5000/api/config
   ```

4. **Update Weights**
   ```bash
   POST http://localhost:5000/api/config/weights
   Content-Type: application/json
   
   {
     "weights": {
       "price": 0.4,
       "commute_time": 0.3,
       ...
     }
   }
   ```

**Using curl:**
```bash
# Score properties
curl -X POST http://localhost:5000/api/score \
  -H "Content-Type: application/json" \
  -d '{
    "work_address": "Times Square, New York, NY",
    "commute_threshold": 30,
    "top_n": 10
  }'

# Health check
curl http://localhost:5000/health
```

**Using Python requests:**
```python
import requests

# Score properties
response = requests.post(
    'http://localhost:5000/api/score',
    json={
        'work_address': 'Times Square, New York, NY',
        'commute_threshold': 30,
        'life_threshold': 15,
        'top_n': 20
    }
)

results = response.json()
print(f"Found {results['count']} properties")
for prop in results['properties']:
    print(f"{prop['ADDRESS']}: Score {prop['SCORE_S_SCORE']:.3f}")
```

**Running API in Docker:**
```bash
# In docker-compose.yml, add API service or run in container
docker exec -it gc-redss-container python src/api.py
```

## Configuration

Edit `src/config.py` to customize:

### Scoring Weights
```python
DEFAULT_SCORING_WEIGHTS = {
    "price": 0.3,
    "commute_time": 0.25,
    "life_accessibility": 0.15,
    "property_size": 0.1,
    "bedrooms": 0.1,
    "bathrooms": 0.1,
}
```

### Spark Configuration
```python
SPARK_CONFIG = {
    "spark.app.name": "GC-REDSS",
    "spark.master": "local[*]",
    "spark.driver.memory": "4g",
    "spark.executor.memory": "4g",
}
```

### Geo-Circle Settings
```python
DEFAULT_COMMUTE_THRESHOLD = 30  # minutes
DEFAULT_LIFE_THRESHOLD = 15     # minutes
DEFAULT_TRANSPORT_MODES = ["driving", "walking", "transit"]
```

### OSMnx Settings
```python
OSMNX_SETTINGS = {
    "network_type": "all",
    "timeout": 180,
    "max_query_area_size": 50 * 1000 * 50 * 1000,
}
```

## Scoring Model

The scoring model uses elastic filtering with the following components:

1. **Price Score** (0.30 weight): Normalized price (lower is better)
2. **Commute Score** (0.25 weight): Based on distance to commute circles
   - Inside circle: score = 1.0
   - Outside circle: score = exp(-penalty_factor * 2)
   - Supports multiple transport modes (driving, walking, transit)
3. **Life Accessibility Score** (0.15 weight): Walking distance to amenities
4. **Property Size Score** (0.10 weight): Normalized square footage
5. **Bedrooms Score** (0.10 weight): Normalized bedroom count
6. **Bathrooms Score** (0.10 weight): Normalized bathroom count

**Final S Score:**
```
S_score = Σ(feature_score × weight)
```

**Elastic Filtering Formula:**
```
If property inside circle:
    score = 1.0
Else:
    distance_to_boundary = calculate_distance(property, circle)
    time_penalty = distance_to_boundary / average_speed
    penalty_factor = time_penalty / threshold_time
    score = exp(-penalty_factor * 2)
```

## Output

The system generates:

1. **Processed data**: `data/processed/processed_houses.parquet`
   - Cleaned and feature-engineered data
   - Parquet format for efficient storage

2. **Scored properties**: `output/scored_properties.parquet`
   - All properties with complete scoring information
   - Includes all original fields + derived features + all scores

3. **Top properties CSV**: `output/top_properties.csv`
   - Human-readable CSV format
   - Top N properties sorted by S Score
   - Easy to import into Excel or other tools

**Output Columns:**
- Original: `ADDRESS`, `PRICE`, `BEDS`, `BATH`, `PROPERTYSQFT`, `LATITUDE`, `LONGITUDE`, etc.
- Derived: `PRICE_PER_SQFT`, `BEDS_PER_BATH`, `BOROUGH`, etc.
- Scores: `SCORE_PRICE_SCORE`, `SCORE_COMMUTE_SCORE`, `SCORE_LIFE_SCORE`, `SCORE_S_SCORE`, etc.

## Technical Stack

- **PySpark**: Big Data processing and distributed computing
- **OSMnx**: OpenStreetMap network analysis and road network extraction
- **NetworkX**: Graph theory for shortest path and route calculation
- **Shapely**: Geometric operations and polygon calculations
- **Geopy**: Geocoding (address to coordinates)
- **Pandas/NumPy**: Data manipulation and numerical operations
- **Flask**: REST API framework (optional)
- **Plotly**: Visualization (for future use)

## Troubleshooting

### ModuleNotFoundError: No module named 'src'

**Solution 1:** Set PYTHONPATH
```bash
export PYTHONPATH=/path/to/project:$PYTHONPATH
python src/main.py ...
```

**Solution 2:** Use module syntax
```bash
python -m src.main ...
```

**Solution 3:** Run from project root
```bash
cd /path/to/project
python src/main.py ...
```

### OSMnx network download is slow

- First run downloads road network data (can take several minutes)
- Network data is cached for subsequent runs
- Consider reducing `max_query_area_size` in config for faster downloads

### Spark memory errors

- Increase memory in `src/config.py`:
  ```python
  "spark.driver.memory": "8g",
  "spark.executor.memory": "8g",
  ```

### API not starting

- Ensure Flask is installed: `pip install flask flask-cors`
- Check port 5000 is not in use
- Run with debug mode: `python src/api.py`

## Future Enhancements

- [ ] SHAP/LIME integration for model interpretability
- [ ] Interactive visualization with Plotly
- [ ] Streamlit/Dash web interface
- [ ] Real-time property updates
- [ ] Advanced clustering analysis
- [ ] Machine learning models for price prediction
- [ ] Integration with real estate APIs (Zillow, Redfin)

## License

This project is for educational purposes.

## References

- Dataset: [New York Housing Market](https://www.kaggle.com/datasets/nelgiriyewithana/new-york-housing-market)
- OSMnx: [Documentation](https://osmnx.readthedocs.io/)
- PySpark: [Documentation](https://spark.apache.org/docs/latest/api/python/)
