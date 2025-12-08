"""
Utility functions for GC-REDSS
"""
import logging
from typing import Dict, Any
import json

logger = logging.getLogger(__name__)


def save_config(config: Dict[str, Any], filepath: str):
    """
    Save configuration to JSON file
    
    Args:
        config: Configuration dictionary
        filepath: Path to save configuration
    """
    try:
        with open(filepath, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info(f"Configuration saved to {filepath}")
    except Exception as e:
        logger.error(f"Error saving configuration: {e}")


def load_config(filepath: str) -> Dict[str, Any]:
    """
    Load configuration from JSON file
    
    Args:
        filepath: Path to configuration file
        
    Returns:
        Configuration dictionary
    """
    try:
        with open(filepath, 'r') as f:
            config = json.load(f)
        logger.info(f"Configuration loaded from {filepath}")
        return config
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        return {}
