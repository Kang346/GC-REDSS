"""
Data acquisition script for downloading dataset from Kaggle
This script handles the entire data acquisition process as required by the project.
"""
import logging
import sys
from pathlib import Path
import shutil

# Add parent directory to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from src.config import RAW_DATA_DIR
except ImportError:
    # Fallback if src module not available
    RAW_DATA_DIR = project_root / "data" / "raw"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def download_kaggle_dataset():
    """
    Download dataset from Kaggle using kagglehub
    
    Returns:
        Path to the downloaded CSV file
    """
    try:
        import kagglehub
        
        logger.info("=" * 80)
        logger.info("Data Acquisition: Downloading NY Housing Market Dataset")
        logger.info("=" * 80)
        
        # Dataset information
        dataset_name = "nelgiriyewithana/new-york-housing-market"
        target_file = "NY-House-Dataset.csv"
        
        logger.info(f"Downloading dataset: {dataset_name}")
        logger.info(f"Target file: {target_file}")
        
        # Download latest version
        download_path = kagglehub.dataset_download(dataset_name)
        logger.info(f"Dataset downloaded to: {download_path}")
        
        # Find the CSV file in the downloaded directory
        csv_file = None
        for file_path in Path(download_path).rglob(target_file):
            if file_path.is_file():
                csv_file = file_path
                break
        
        if csv_file is None:
            # Try to find any CSV file
            csv_files = list(Path(download_path).rglob("*.csv"))
            if csv_files:
                csv_file = csv_files[0]
                logger.warning(f"Target file '{target_file}' not found, using: {csv_file.name}")
            else:
                raise FileNotFoundError(f"Could not find CSV file in {download_path}")
        
        # Ensure raw data directory exists
        RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        
        # Copy CSV file to data/raw directory
        target_path = RAW_DATA_DIR / target_file
        logger.info(f"Copying {csv_file.name} to {target_path}")
        shutil.copy2(csv_file, target_path)
        
        logger.info("=" * 80)
        logger.info(f"✓ Dataset successfully downloaded and saved to: {target_path}")
        logger.info(f"✓ File size: {target_path.stat().st_size / (1024*1024):.2f} MB")
        logger.info("=" * 80)
        
        return str(target_path)
        
    except ImportError:
        logger.error("kagglehub is not installed. Please install it using:")
        logger.error("  pip install kagglehub")
        raise
    except Exception as e:
        logger.error(f"Error downloading dataset: {e}", exc_info=True)
        raise


def check_dataset_exists():
    """
    Check if dataset already exists in data/raw directory
    
    Returns:
        Path to existing file if found, None otherwise
    """
    target_file = RAW_DATA_DIR / "NY-House-Dataset.csv"
    if target_file.exists():
        logger.info(f"Dataset already exists at: {target_file}")
        logger.info(f"File size: {target_file.stat().st_size / (1024*1024):.2f} MB")
        return str(target_file)
    return None


def main():
    """Main function"""
    # Check if dataset already exists
    existing_file = check_dataset_exists()
    if existing_file:
        response = input("Dataset already exists. Download again? (y/n): ")
        if response.lower() != 'y':
            logger.info("Using existing dataset.")
            return existing_file
    
    # Download dataset
    try:
        file_path = download_kaggle_dataset()
        logger.info("\n✓ Data acquisition completed successfully!")
        return file_path
    except Exception as e:
        logger.error(f"\n✗ Data acquisition failed: {e}")
        logger.error("\nTroubleshooting:")
        logger.error("1. Ensure kagglehub is installed: pip install kagglehub")
        logger.error("2. Check your internet connection")
        logger.error("3. Verify Kaggle dataset name is correct")
        sys.exit(1)


if __name__ == "__main__":
    main()

