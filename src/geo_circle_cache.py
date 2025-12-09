"""
Cache manager for geo-circle calculations to improve response time
"""
import json
import hashlib
import pickle
from pathlib import Path
from typing import Dict, Optional, Tuple
import logging

from src.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

CACHE_DIR = PROJECT_ROOT / "cache" / "geo_circles"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


class GeoCircleCache:
    """Cache manager for commute and life circles"""
    
    def __init__(self):
        self.cache_dir = CACHE_DIR
        logger.info(f"GeoCircleCache initialized, cache directory: {self.cache_dir}")
    
    def _get_cache_key(self, work_address: str, commute_threshold: float, 
                      life_threshold: float, transport_modes: list) -> str:
        """Generate cache key from parameters"""
        key_string = f"{work_address}_{commute_threshold}_{life_threshold}_{sorted(transport_modes)}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def get_cached_circles(self, work_address: str, commute_threshold: float,
                          life_threshold: float, transport_modes: list) -> Optional[Dict]:
        """Get cached commute and life circles if available"""
        cache_key = self._get_cache_key(work_address, commute_threshold, life_threshold, transport_modes)
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        
        if cache_file.exists():
            try:
                logger.info(f"Loading cached circles from {cache_file}")
                with open(cache_file, 'rb') as f:
                    return pickle.load(f)
            except Exception as e:
                logger.warning(f"Error loading cache: {e}")
                return None
        return None
    
    def save_circles(self, work_address: str, commute_threshold: float,
                    life_threshold: float, transport_modes: list,
                    commute_circles: Dict, life_circle: any):
        """Save commute and life circles to cache"""
        cache_key = self._get_cache_key(work_address, commute_threshold, life_threshold, transport_modes)
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        
        try:
            cache_data = {
                'commute_circles': commute_circles,
                'life_circle': life_circle,
                'work_address': work_address,
                'commute_threshold': commute_threshold,
                'life_threshold': life_threshold,
            }
            with open(cache_file, 'wb') as f:
                pickle.dump(cache_data, f)
            logger.info(f"Cached circles saved to {cache_file}")
        except Exception as e:
            logger.warning(f"Error saving cache: {e}")

