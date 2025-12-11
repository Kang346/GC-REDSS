"""
Elastic filtering scoring model for real estate properties
"""
import numpy as np
import pandas as pd
from pyspark.sql import DataFrame
from pyspark.sql.functions import col, when, lit, udf, min as spark_min, max as spark_max
from pyspark.sql.types import DoubleType, StringType
from typing import Dict, List, Tuple, Optional
import logging
import pickle
import base64

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
        
        # Transport mode speeds (km/h) - realistic speeds for Manhattan (reduced)
        mode_speeds = {
            "driving": 10,  # Manhattan average is 8-10 km/h due to heavy traffic (regular: 10, highway: 15)
            "walking": 3.3, # Reduced proportionally (4 * 10/12)
            "transit": 8.3, # Reduced proportionally (10 * 10/12)
            "biking": 8.3,  # Reduced proportionally (10 * 10/12)
            "subway": 25,   # Subway average speed in Manhattan (including stops)
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
    
    def _serialize_polygon(self, polygon) -> str:
        """
        Serialize Shapely Polygon to base64-encoded pickle string for Spark UDF
        
        Args:
            polygon: Shapely Polygon object
            
        Returns:
            Base64-encoded pickle string
        """
        if polygon is None:
            return None
        return base64.b64encode(pickle.dumps(polygon)).decode('utf-8')
    
    def _deserialize_polygon(self, polygon_str: str):
        """
        Deserialize base64-encoded pickle string back to Shapely Polygon
        
        Args:
            polygon_str: Base64-encoded pickle string
            
        Returns:
            Shapely Polygon object
        """
        if polygon_str is None:
            return None
        return pickle.loads(base64.b64decode(polygon_str.encode('utf-8')))
    
    def _create_commute_score_udf(self, commute_circles: Dict[str, any], 
                                   commute_threshold: float):
        """
        Create Spark UDF for calculating commute scores in parallel
        
        Args:
            commute_circles: Dictionary of transport mode -> isochrone polygon
            commute_threshold: Maximum acceptable commute time (minutes)
            
        Returns:
            Spark UDF function
        """
        # Serialize polygons for transmission to Spark workers
        commute_circles_serialized = {}
        for mode, circle in commute_circles.items():
            if circle is not None:
                commute_circles_serialized[mode] = self._serialize_polygon(circle)
        
        # Transport mode speeds
        mode_speeds = {
            "driving": 10,
            "walking": 3.3,
            "transit": 8.3,
            "biking": 8.3,
            "subway": 25,
        }
        
        def calculate_commute_score_udf(lat: float, lon: float) -> float:
            """UDF function to calculate commute score"""
            import math
            import pickle
            import base64
            from shapely.geometry import Point
            from geopy.distance import geodesic
            
            if lat is None or lon is None or (math.isnan(lat) if lat is not None else True) or (math.isnan(lon) if lon is not None else True):
                return 0.0
            
            property_point = (lat, lon)
            in_circle_scores = []
            
            for mode, circle_str in commute_circles_serialized.items():
                if circle_str is None:
                    continue
                
                # Deserialize polygon (inline to work in Spark worker nodes)
                try:
                    circle = pickle.loads(base64.b64decode(circle_str.encode('utf-8')))
                except:
                    continue
                
                if circle is None:
                    continue
                
                # Check if point is in circle
                point_geom = Point(lon, lat)
                if circle.contains(point_geom) or circle.touches(point_geom):
                    in_circle_scores.append(1.0)
                else:
                    # Calculate distance to boundary
                    try:
                        nearest_point_on_boundary = circle.boundary.interpolate(
                            circle.boundary.project(point_geom)
                        )
                        boundary_coords = (nearest_point_on_boundary.y, nearest_point_on_boundary.x)
                        distance_km = geodesic(property_point, boundary_coords).kilometers
                    except:
                        distance_degrees = circle.boundary.distance(point_geom)
                        distance_km = distance_degrees * 111
                    
                    # Calculate score
                    speed_kmh = mode_speeds.get(mode, 30)
                    time_penalty_minutes = (distance_km / speed_kmh) * 60
                    penalty_factor = time_penalty_minutes / commute_threshold
                    score = 1.0 / (1.0 + penalty_factor ** 1.2)
                    score = max(0.05, score)
                    in_circle_scores.append(score)
            
            return max(in_circle_scores) if in_circle_scores else 0.01
        
        return udf(calculate_commute_score_udf, DoubleType())
    
    def _create_life_score_udf(self, life_circle: any, life_threshold: float):
        """
        Create Spark UDF for calculating life accessibility scores in parallel
        
        Args:
            life_circle: Isochrone polygon for life accessibility
            life_threshold: Maximum acceptable walking time (minutes)
            
        Returns:
            Spark UDF function
        """
        if life_circle is None:
            return None
        
        # Serialize polygon
        life_circle_serialized = self._serialize_polygon(life_circle)
        
        def calculate_life_score_udf(lat: float, lon: float) -> float:
            """UDF function to calculate life score"""
            import math
            import pickle
            import base64
            from shapely.geometry import Point
            from geopy.distance import geodesic
            
            if lat is None or lon is None or (math.isnan(lat) if lat is not None else True) or (math.isnan(lon) if lon is not None else True):
                return 0.0
            
            if life_circle_serialized is None:
                return 0.5
            
            # Deserialize polygon (inline to work in Spark worker nodes)
            try:
                circle = pickle.loads(base64.b64decode(life_circle_serialized.encode('utf-8')))
            except:
                return 0.5
            
            if circle is None:
                return 0.5
            
            property_point = (lat, lon)
            point_geom = Point(lon, lat)
            
            if circle.contains(point_geom) or circle.touches(point_geom):
                return 1.0
            else:
                # Calculate distance to boundary
                try:
                    nearest_point_on_boundary = circle.boundary.interpolate(
                        circle.boundary.project(point_geom)
                    )
                    boundary_coords = (nearest_point_on_boundary.y, nearest_point_on_boundary.x)
                    distance_km = geodesic(property_point, boundary_coords).kilometers
                except:
                    distance_degrees = circle.boundary.distance(point_geom)
                    distance_km = distance_degrees * 111
                
                time_penalty_minutes = (distance_km / 5) * 60
                penalty_factor = time_penalty_minutes / life_threshold
                score = 1.0 / (1.0 + penalty_factor ** 1.2)
                return max(0.05, score)
        
        return udf(calculate_life_score_udf, DoubleType())
    
    def _normalize_feature_spark(self, df: DataFrame, col_name: str, 
                                  reverse: bool = False) -> DataFrame:
        """
        Normalize a feature column using Spark operations (parallel)
        
        Args:
            df: Spark DataFrame
            col_name: Name of column to normalize
            reverse: If True, reverse the scale (higher values = lower score)
            
        Returns:
            DataFrame with normalized column added as {col_name}_score
        """
        from pyspark.sql.functions import col, when, isnan, isnull
        
        if col_name not in df.columns:
            return df
        
        # Calculate min and max using Spark aggregations (parallel)
        stats = df.select(
            spark_min(col(col_name)).alias("min_val"),
            spark_max(col(col_name)).alias("max_val")
        ).collect()[0]
        
        min_val = stats["min_val"]
        max_val = stats["max_val"]
        
        if min_val is None or max_val is None or min_val == max_val:
            # Return default score
            return df.withColumn(f"{col_name.lower()}_score", lit(0.5))
        
        # Normalize: (value - min) / (max - min)
        normalized = (col(col_name) - lit(min_val)) / lit(max_val - min_val)
        
        if reverse:
            normalized = lit(1.0) - normalized
        
        # Clip to [0, 1]
        normalized = when(normalized < 0, 0.0).when(normalized > 1, 1.0).otherwise(normalized)
        
        return df.withColumn(f"{col_name.lower()}_score", normalized)
    
    def score_properties(self,
                        properties_df: DataFrame,
                        work_address: str,
                        commute_threshold_minutes: float,
                        life_threshold_minutes: float = 15,
                        transport_modes: List[str] = None,
                        fast_mode: bool = True) -> DataFrame:
        """
        Calculate comprehensive S scores for all properties using Spark parallel processing
        
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
        logger.info("Calculating scores for properties using Spark parallel processing...")
        
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
        
        # Start with the input DataFrame
        result_df = properties_df
        
        # Calculate commute score using Spark UDF (parallel processing)
        logger.info("Calculating commute scores in parallel using Spark UDF...")
        commute_score_udf = self._create_commute_score_udf(
            commute_circles, 
            commute_threshold_minutes
        )
        result_df = result_df.withColumn(
            "commute_score",
            commute_score_udf(col("LATITUDE"), col("LONGITUDE"))
        )
        
        # Calculate life accessibility score using Spark UDF (parallel processing)
        if life_circle:
            logger.info("Calculating life accessibility scores in parallel using Spark UDF...")
            life_score_udf = self._create_life_score_udf(life_circle, life_threshold_minutes)
            result_df = result_df.withColumn(
                "life_score",
                life_score_udf(col("LATITUDE"), col("LONGITUDE"))
            )
        else:
            result_df = result_df.withColumn("life_score", lit(0.5))
        
        # Calculate feature scores using Spark operations (parallel)
        logger.info("Calculating feature scores in parallel using Spark operations...")
        
        # Price score (lower is better, so reverse=True)
        if "PRICE" in result_df.columns:
            result_df = self._normalize_feature_spark(result_df, "PRICE", reverse=True)
        
        # Property size score
        if "PROPERTYSQFT" in result_df.columns:
            result_df = self._normalize_feature_spark(result_df, "PROPERTYSQFT", reverse=False)
        
        # Bedrooms score
        if "BEDS" in result_df.columns:
            result_df = self._normalize_feature_spark(result_df, "BEDS", reverse=False)
        
        # Bathrooms score
        if "BATH" in result_df.columns:
            result_df = self._normalize_feature_spark(result_df, "BATH", reverse=False)
        
        # Calculate weighted S score using Spark operations
        logger.info("Calculating final S scores...")
        s_score = (
            col("price_score") * lit(self.weights.get("price", 0)) +
            col("commute_score") * lit(self.weights.get("commute_time", 0)) +
            col("life_score") * lit(self.weights.get("life_accessibility", 0)) +
            when(col("propertysqft_score").isNotNull(), col("propertysqft_score")).otherwise(lit(0.0)) * lit(self.weights.get("property_size", 0)) +
            when(col("beds_score").isNotNull(), col("beds_score")).otherwise(lit(0.0)) * lit(self.weights.get("bedrooms", 0)) +
            when(col("bath_score").isNotNull(), col("bath_score")).otherwise(lit(0.0)) * lit(self.weights.get("bathrooms", 0))
        )
        result_df = result_df.withColumn("S_score", s_score)
        
        # Rename score columns to SCORE_* format for consistency
        score_columns = {
            "price_score": "SCORE_PRICE_SCORE",
            "commute_score": "SCORE_COMMUTE_SCORE",
            "life_score": "SCORE_LIFE_SCORE",
            "propertysqft_score": "SCORE_SIZE_SCORE",
            "beds_score": "SCORE_BEDROOMS_SCORE",
            "bath_score": "SCORE_BATHROOMS_SCORE",
            "S_score": "SCORE_S_SCORE"
        }
        
        for old_name, new_name in score_columns.items():
            if old_name in result_df.columns:
                result_df = result_df.withColumnRenamed(old_name, new_name)
        
        logger.info("Scoring completed using Spark parallel processing")
        return result_df
