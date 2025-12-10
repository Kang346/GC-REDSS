"""
Basic test script to verify installation and basic functionality
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test if all modules can be imported"""
    print("Testing imports...")
    try:
        from src import config
        print("✓ config module imported")
        
        from src.data_processor import DataProcessor
        print("✓ DataProcessor imported")
        
        from src.geo_circle import GeoCircleCalculator
        print("✓ GeoCircleCalculator imported")
        
        from src.scoring_model import ScoringModel
        print("✓ ScoringModel imported")
        
        print("\nAll imports successful!")
        return True
    except Exception as e:
        print(f"✗ Import error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_config():
    """Test configuration loading"""
    print("\nTesting configuration...")
    try:
        from src.config import (
            PROJECT_ROOT, DATA_DIR, SPARK_CONFIG,
            DEFAULT_SCORING_WEIGHTS
        )
        print(f"✓ Project root: {PROJECT_ROOT}")
        print(f"✓ Data directory: {DATA_DIR}")
        print(f"✓ Spark config loaded")
        print(f"✓ Default weights: {DEFAULT_SCORING_WEIGHTS}")
        return True
    except Exception as e:
        print(f"✗ Configuration error: {e}")
        return False

def test_data_file():
    """Test if data file exists"""
    print("\nTesting data file...")
    try:
        from src.config import RAW_DATA_DIR
        data_file = RAW_DATA_DIR / "NY-House-Dataset.csv"
        if data_file.exists():
            print(f"✓ Data file found: {data_file}")
            return True
        else:
            print(f"✗ Data file not found: {data_file}")
            print("  Please ensure NY-House-Dataset.csv is in data/raw/")
            return False
    except Exception as e:
        print(f"✗ Data file check error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("GC-REDSS Basic Test")
    print("=" * 60)
    
    results = []
    results.append(test_imports())
    results.append(test_config())
    results.append(test_data_file())
    
    print("\n" + "=" * 60)
    if all(results):
        print("All tests passed! ✓")
        print("=" * 60)
        sys.exit(0)
    else:
        print("Some tests failed. Please check the errors above.")
        print("=" * 60)
        sys.exit(1)
