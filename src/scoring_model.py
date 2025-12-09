"""
Elastic filtering scoring model for real estate properties
"""
import numpy as np
import pandas as pd
from pyspark.sql import DataFrame
from pyspark.sql.functions import col, when, lit, udf
from pyspark.sql.types import DoubleType
from typing import Dict, List, Tuple, Optional
import logging

from src.config import DEFAULT_SCORING_WEIGHTS
from src.geo_circle import GeoCircleCalculator
from src.geo_circle_cache import GeoCircleCache

logger = logging.getLogger(__name__)


class ScoringModel:
    """
    Elastic filtering scoring model that provides adjustable S scores
    instead of hard thresholds
    """
    
    def __init__(self, weights: Dict[str, float] = None):
        """
        Initialize scoring model
        
        Args:
            weights: Dictionary of feature weights. If None, uses defaults.
        """
        self.weights = weights or DEFAULT_SCORING_WEIGHTS.copy()
        self._normalize_weights()
        self.geo_calculator = GeoCircleCalculator()
        self.cache = GeoCircleCache()
        logger.info(f"ScoringModel initialized with weights: {self.weights}")
    
    def _normalize_weights(self):
        """Normalize weights to sum to 1.0"""
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}
    
    def normalize_feature(self, values: np.ndarray, 
                         min_val: float = None, 
                         max_val: float = None,
                         reverse: bool = False) -> np.ndarray:
        """
        Normalize feature values to [0, 1] range
        
        Args:
            values: Array of feature values
            min_val: Minimum value for normalization (if None, uses min of values)
            max_val: Maximum value for normalization (if None, uses max of values)
            reverse: If True, reverse the scale (higher values = lower score)
            
        Returns:
            Normalized array
        """
        if min_val is None:
            min_val = np.nanmin(values)
        if max_val is None:
            max_val = np.nanmax(values)
        
        if max_val == min_val:
            return np.ones_like(values) * 0.5
        
        normalized = (values - min_val) / (max_val - min_val)
        
        if reverse:
            normalized = 1 - normalized
        
        # Clip to [0, 1]
        normalized = np.clip(normalized, 0, 1)
        
        return normalized
    
    def calculate_commute_score(self,
                               property_lat: float,
                               property_lon: float,
                               commute_circles: Dict[str, any],
                               commute_threshold: float) -> float:
        """
        Calculate commute accessibility score using elastic filtering
        Score gradually decreases from 1.0 to near 0 as distance increases
        
        Args:
            property_lat: Property latitude
            property_lon: Property longitude
            commute_circles: Dictionary of transport mode -> isochrone polygon
            commute_threshold: Maximum acceptable commute time (minutes)
            
        Returns:
            Commute score between 0 and 1
        """
        from shapely.geometry import Point
        from geopy.distance import geodesic
        
        property_point = (property_lat, property_lon)
        
        # Transport mode speeds (km/h)
        mode_speeds = {
            "driving": 50,
            "walking": 5,
            "transit": 30,
            "biking": 15  # Average urban cycling speed
        }
        
        # Check if property is within any commute circle
        in_circle_scores = []
        for mode, circle in commute_circles.items():
            if self.geo_calculator.check_point_in_circle(property_point, circle):
                in_circle_scores.append(1.0)
            else:
                # Calculate accurate geodesic distance to circle boundary
                point_geom = Point(property_lon, property_lat)
                
                # Find nearest point on circle boundary for accurate distance calculation
                try:
                    # Get the actual nearest point on the boundary (more accurate than midpoint)
                    # Project the point onto the boundary to find closest point
                    nearest_point_on_boundary = circle.boundary.interpolate(
                        circle.boundary.project(point_geom)
                    )
                    boundary_coords = (nearest_point_on_boundary.y, nearest_point_on_boundary.x)  # lat, lon
                    
                    # Calculate accurate geodesic distance in kilometers
                    distance_km = geodesic(property_point, boundary_coords).kilometers
                except:
                    # Fallback: use Shapely distance (in degrees) and convert
                    distance_degrees = circle.boundary.distance(point_geom)
                    # Approximate conversion (1 degree ≈ 111km at equator)
                    distance_km = distance_degrees * 111
                
                # Calculate time penalty based on transport mode speed
                speed_kmh = mode_speeds.get(mode, 30)
                time_penalty_minutes = (distance_km / speed_kmh) * 60
                
                # IMPROVED elastic filtering: much more flexible boundary
                # Allow properties even 2x beyond threshold to still have decent scores
                # This addresses user feedback: "Even slightly beyond 15 minutes should be reachable"
                
                penalty_factor = time_penalty_minutes / commute_threshold
                
                # More lenient decay: properties up to 2x threshold still get reasonable scores
                # Formula: 1 / (1 + penalty_factor^1.2) - gentler decay
                # For penalty_factor = 1.0 (exactly at threshold): score ≈ 0.45
                # For penalty_factor = 2.0 (2x threshold): score ≈ 0.30
                # This ensures properties just outside circle still appear in results
                score = 1.0 / (1.0 + penalty_factor ** 1.2)
                
                # Ensure minimum score is higher (0.05 instead of 0.01)
                # This ensures even far properties have some visibility
                score = max(0.05, score)
                
                in_circle_scores.append(score)
        
        # Return maximum score across all transport modes
        return max(in_circle_scores) if in_circle_scores else 0.01
    
    def calculate_life_score(self,
                            property_lat: float,
                            property_lon: float,
                            life_circle: any,
                            life_threshold: float) -> float:
        """
        Calculate life accessibility score with smooth gradual decay
        
        Args:
            property_lat: Property latitude
            property_lon: Property longitude
            life_circle: Isochrone polygon for life accessibility
            life_threshold: Maximum acceptable walking time (minutes)
            
        Returns:
            Life accessibility score between 0 and 1
        """
        from shapely.geometry import Point
        from geopy.distance import geodesic
        
        property_point = (property_lat, property_lon)
        
        if self.geo_calculator.check_point_in_circle(property_point, life_circle):
            return 1.0
        else:
            # Calculate accurate geodesic distance to circle boundary
            point_geom = Point(property_lon, property_lat)
            
            try:
                # Get the actual nearest point on the boundary (more accurate than midpoint)
                nearest_point_on_boundary = life_circle.boundary.interpolate(
                    life_circle.boundary.project(point_geom)
                )
                boundary_coords = (nearest_point_on_boundary.y, nearest_point_on_boundary.x)
                
                # Calculate accurate geodesic distance in kilometers
                distance_km = geodesic(property_point, boundary_coords).kilometers
            except:
                # Fallback: use Shapely distance (in degrees) and convert
                distance_degrees = life_circle.boundary.distance(point_geom)
                # Approximate conversion (1 degree ≈ 111km at equator)
                distance_km = distance_degrees * 111
            
            # Walking speed: ~5 km/h
            time_penalty_minutes = (distance_km / 5) * 60
            
            # IMPROVED: More flexible boundary for life accessibility
            # Allow properties even 2x beyond threshold to still have decent scores
            penalty_factor = time_penalty_minutes / life_threshold
            score = 1.0 / (1.0 + penalty_factor ** 1.2)  # Gentler decay
            
            # Ensure minimum score is higher
            return max(0.05, score)
    
    def score_properties(self,
                        properties_df: DataFrame,
                        work_address: str,
                        commute_threshold_minutes: float,
                        life_threshold_minutes: float = 15,
                        transport_modes: List[str] = None,
                        fast_mode: bool = True) -> DataFrame:
        """
        Calculate comprehensive S scores for all properties
        
        Args:
            properties_df: Spark DataFrame with property data
            work_address: Address of workplace
            commute_threshold_minutes: Maximum acceptable commute time
            life_threshold_minutes: Maximum acceptable walking time to amenities
            transport_modes: List of transport modes to consider
            fast_mode: If True, use cached circles or simplified calculation (faster)
            
        Returns:
            DataFrame with additional score columns
        """
        logger.info("Calculating scores for properties...")
        
        if transport_modes is None:
            transport_modes = ["driving"]  # Default to driving only for faster response
        
        # Try to get cached circles first (fast mode)
        commute_circles = None
        life_circle = None
        
        if fast_mode:
            cached = self.cache.get_cached_circles(
                work_address, commute_threshold_minutes, 
                life_threshold_minutes, transport_modes
            )
            if cached:
                logger.info("Using cached geo-circles (fast mode)")
                commute_circles = cached['commute_circles']
                life_circle = cached['life_circle']
        
        # If not cached, calculate circles
        if commute_circles is None:
            if fast_mode:
                logger.info("⚡ FAST MODE: Using simplified calculation (~1-2 seconds)")
            else:
                logger.info("Calculating new geo-circles (this may take 3-5 minutes)...")
            
            commute_circles = self.geo_calculator.calculate_commute_circle(
                work_address,
                commute_threshold_minutes,
                transport_modes,
                fast_mode=fast_mode
            )
            
            # For life circle, use work address as center (more logical)
            work_location = self.geo_calculator.geocode_address(work_address)
            if fast_mode:
                # Fast mode: use circular buffer
                life_circle = self.geo_calculator._create_circular_buffer(
                    work_location,
                    life_threshold_minutes,
                    "walking"
                )
            else:
                life_center = f"{work_location[0]},{work_location[1]}"
                life_circle = self.geo_calculator.calculate_life_circle(
                    life_center,
                    life_threshold_minutes
                )
            
            # Save to cache for next time (only if not fast mode, to avoid caching simplified circles)
            if not fast_mode:
                self.cache.save_circles(
                    work_address, commute_threshold_minutes,
                    life_threshold_minutes, transport_modes,
                    commute_circles, life_circle
                )
        
        # Convert Spark DataFrame to Pandas for easier processing
        # (For large datasets, you'd want to use Spark UDFs instead)
        properties_pd = properties_df.toPandas()
        
        # Calculate individual feature scores
        scores = pd.DataFrame(index=properties_pd.index)
        
        # Price score (lower is better, so reverse=True)
        if "PRICE" in properties_pd.columns:
            prices = properties_pd["PRICE"].values
            scores["price_score"] = self.normalize_feature(prices, reverse=True)
        
        # Commute score
        commute_scores = []
        for idx, row in properties_pd.iterrows():
            if pd.notna(row["LATITUDE"]) and pd.notna(row["LONGITUDE"]):
                score = self.calculate_commute_score(
                    row["LATITUDE"],
                    row["LONGITUDE"],
                    commute_circles,
                    commute_threshold_minutes
                )
                commute_scores.append(score)
            else:
                commute_scores.append(0.0)
        scores["commute_score"] = commute_scores
        
        # Life accessibility score
        if life_circle:
            life_scores = []
            for idx, row in properties_pd.iterrows():
                if pd.notna(row["LATITUDE"]) and pd.notna(row["LONGITUDE"]):
                    score = self.calculate_life_score(
                        row["LATITUDE"],
                        row["LONGITUDE"],
                        life_circle,
                        life_threshold_minutes
                    )
                    life_scores.append(score)
                else:
                    life_scores.append(0.0)
            scores["life_score"] = life_scores
        else:
            scores["life_score"] = 0.5  # Default neutral score
        
        # Property size score
        if "PROPERTYSQFT" in properties_pd.columns:
            sqft = properties_pd["PROPERTYSQFT"].values
            scores["size_score"] = self.normalize_feature(sqft, reverse=False)
        
        # Bedrooms score
        if "BEDS" in properties_pd.columns:
            beds = properties_pd["BEDS"].values
            scores["bedrooms_score"] = self.normalize_feature(beds, reverse=False)
        
        # Bathrooms score
        if "BATH" in properties_pd.columns:
            baths = properties_pd["BATH"].values
            scores["bathrooms_score"] = self.normalize_feature(baths, reverse=False)
        
        # Calculate weighted S score
        s_score = (
            scores.get("price_score", 0) * self.weights.get("price", 0) +
            scores.get("commute_score", 0) * self.weights.get("commute_time", 0) +
            scores.get("life_score", 0) * self.weights.get("life_accessibility", 0) +
            scores.get("size_score", 0) * self.weights.get("property_size", 0) +
            scores.get("bedrooms_score", 0) * self.weights.get("bedrooms", 0) +
            scores.get("bathrooms_score", 0) * self.weights.get("bathrooms", 0)
        )
        scores["S_score"] = s_score
        
        # Add scores back to properties DataFrame
        for col_name in scores.columns:
            properties_pd[f"SCORE_{col_name.upper()}"] = scores[col_name].values
        
        # Convert back to Spark DataFrame
        from pyspark.sql import SparkSession
        spark = SparkSession.getActiveSession()
        if spark is None:
            spark = properties_df.sql_ctx.sparkSession
        
        result_df = spark.createDataFrame(properties_pd)
        
        logger.info("Scoring completed")
        return result_df
