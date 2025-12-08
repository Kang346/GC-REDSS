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
        
        Args:
            property_lat: Property latitude
            property_lon: Property longitude
            commute_circles: Dictionary of transport mode -> isochrone polygon
            commute_threshold: Maximum acceptable commute time (minutes)
            
        Returns:
            Commute score between 0 and 1
        """
        property_point = (property_lat, property_lon)
        
        # Check if property is within any commute circle
        in_circle_scores = []
        for mode, circle in commute_circles.items():
            if self.geo_calculator.check_point_in_circle(property_point, circle):
                in_circle_scores.append(1.0)
            else:
                # Elastic filtering: calculate distance to circle boundary
                from shapely.geometry import Point
                point_geom = Point(property_lon, property_lat)
                distance_to_boundary = circle.boundary.distance(point_geom)
                
                # Convert distance to approximate time penalty
                # Rough conversion: 1 degree ≈ 111km, assume average speed
                distance_km = distance_to_boundary * 111
                time_penalty = distance_km / 50 * 60  # Assume 50 km/h, convert to minutes
                
                # Elastic score: exponential decay outside circle
                # Score = 1.0 if inside, decays to 0 as distance increases
                penalty_factor = time_penalty / commute_threshold
                score = np.exp(-penalty_factor * 2)  # Exponential decay
                in_circle_scores.append(score)
        
        # Return maximum score across all transport modes
        return max(in_circle_scores) if in_circle_scores else 0.0
    
    def calculate_life_score(self,
                            property_lat: float,
                            property_lon: float,
                            life_circle: any,
                            life_threshold: float) -> float:
        """
        Calculate life accessibility score
        
        Args:
            property_lat: Property latitude
            property_lon: Property longitude
            life_circle: Isochrone polygon for life accessibility
            life_threshold: Maximum acceptable walking time (minutes)
            
        Returns:
            Life accessibility score between 0 and 1
        """
        property_point = (property_lat, property_lon)
        
        if self.geo_calculator.check_point_in_circle(property_point, life_circle):
            return 1.0
        else:
            # Elastic filtering for life circle
            from shapely.geometry import Point
            point_geom = Point(property_lon, property_lat)
            distance_to_boundary = life_circle.boundary.distance(point_geom)
            
            # Walking speed: ~5 km/h
            distance_km = distance_to_boundary * 111
            time_penalty = distance_km / 5 * 60  # Convert to minutes
            
            penalty_factor = time_penalty / life_threshold
            score = np.exp(-penalty_factor * 2)
            
            return max(0.0, score)
    
    def score_properties(self,
                        properties_df: DataFrame,
                        work_address: str,
                        commute_threshold_minutes: float,
                        life_threshold_minutes: float = 15,
                        transport_modes: List[str] = None) -> DataFrame:
        """
        Calculate comprehensive S scores for all properties
        
        Args:
            properties_df: Spark DataFrame with property data
            work_address: Address of workplace
            commute_threshold_minutes: Maximum acceptable commute time
            life_threshold_minutes: Maximum acceptable walking time to amenities
            transport_modes: List of transport modes to consider
            
        Returns:
            DataFrame with additional score columns
        """
        logger.info("Calculating scores for properties...")
        
        # Calculate commute circles
        commute_circles = self.geo_calculator.calculate_commute_circle(
            work_address,
            commute_threshold_minutes,
            transport_modes
        )
        
        # For life circle, we'll use a representative property location
        # In practice, you might want to calculate this per property or use a centroid
        sample_property = properties_df.select("LATITUDE", "LONGITUDE").first()
        if sample_property:
            life_center = f"{sample_property['LATITUDE']},{sample_property['LONGITUDE']}"
            life_circle = self.geo_calculator.calculate_life_circle(
                life_center,
                life_threshold_minutes
            )
        else:
            life_circle = None
        
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
