"""
Geo-Circle (Isochrone) calculation module for commute and life accessibility zones
"""
import osmnx as ox
import networkx as nx
import numpy as np
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
import logging
from typing import List, Tuple, Dict, Optional
import pandas as pd

from src.config import OSMNX_SETTINGS

logger = logging.getLogger(__name__)


class GeoCircleCalculator:
    """Calculate isochrones (geo-circles) for commute and life accessibility"""
    
    def __init__(self):
        """Initialize GeoCircleCalculator"""
        self.geolocator = Nominatim(user_agent="gc-redss")
        self.graph_cache = {}
        logger.info("GeoCircleCalculator initialized")
    
    def geocode_address(self, address: str) -> Tuple[float, float]:
        """
        Convert address to coordinates
        
        Args:
            address: Address string
            
        Returns:
            Tuple of (latitude, longitude)
        """
        try:
            location = self.geolocator.geocode(address, timeout=10)
            if location:
                return (location.latitude, location.longitude)
            else:
                raise ValueError(f"Could not geocode address: {address}")
        except Exception as e:
            logger.error(f"Geocoding error for {address}: {e}")
            raise
    
    def get_road_network(self, center_point: Tuple[float, float], 
                        distance: float = 5000) -> nx.MultiDiGraph:
        """
        Download and cache road network from OpenStreetMap
        
        Args:
            center_point: (latitude, longitude) center point
            distance: Distance in meters to extend network
            
        Returns:
            NetworkX graph of road network
        """
        cache_key = f"{center_point[0]:.4f}_{center_point[1]:.4f}_{distance}"
        
        if cache_key in self.graph_cache:
            logger.info(f"Using cached network for {cache_key}")
            return self.graph_cache[cache_key]
        
        try:
            logger.info(f"Downloading road network for {center_point}")
            G = ox.graph_from_point(
                center_point,
                dist=distance,
                network_type=OSMNX_SETTINGS["network_type"],
                simplify=True
            )
            
            # Add edge travel times based on speed limits and road types
            G = ox.add_edge_speeds(G)
            G = ox.add_edge_travel_times(G)
            
            self.graph_cache[cache_key] = G
            logger.info(f"Network downloaded: {len(G.nodes)} nodes, {len(G.edges)} edges")
            return G
            
        except Exception as e:
            logger.error(f"Error downloading network: {e}")
            # Fallback to simple distance-based calculation
            return None
    
    def calculate_isochrone(self, 
                           center_point: Tuple[float, float],
                           travel_time_minutes: float,
                           transport_mode: str = "driving") -> Polygon:
        """
        Calculate isochrone polygon for given travel time
        
        Args:
            center_point: (latitude, longitude) starting point
            travel_time_minutes: Maximum travel time in minutes
            transport_mode: 'driving', 'walking', or 'transit'
            
        Returns:
            Shapely Polygon representing the isochrone
        """
        try:
            # Get road network
            distance_estimate = travel_time_minutes * 1000 / 60  # Rough estimate in meters
            G = self.get_road_network(center_point, distance=distance_estimate * 2)
            
            if G is None:
                # Fallback: create circular buffer
                logger.warning("Using fallback circular buffer")
                return self._create_circular_buffer(center_point, travel_time_minutes, transport_mode)
            
            # Find nearest node to center point
            center_node = ox.distance.nearest_nodes(G, center_point[1], center_point[0])
            
            # Calculate travel times from center node
            travel_times = {}
            for node in G.nodes():
                try:
                    if transport_mode == "walking":
                        # Walking speed: ~5 km/h
                        path = nx.shortest_path(G, center_node, node, weight='length')
                        total_length = sum(G[u][v][0].get('length', 0) for u, v in zip(path[:-1], path[1:]))
                        time_seconds = (total_length / 1000) / 5 * 3600  # Convert to seconds
                    elif transport_mode == "transit":
                        # Transit: assume average 30 km/h including stops
                        path = nx.shortest_path(G, center_node, node, weight='length')
                        total_length = sum(G[u][v][0].get('length', 0) for u, v in zip(path[:-1], path[1:]))
                        time_seconds = (total_length / 1000) / 30 * 3600
                    else:  # driving
                        # Use travel_time if available, otherwise estimate
                        try:
                            time_seconds = nx.shortest_path_length(
                                G, center_node, node, weight='travel_time'
                            )
                        except:
                            path = nx.shortest_path(G, center_node, node, weight='length')
                            total_length = sum(G[u][v][0].get('length', 0) for u, v in zip(path[:-1], path[1:]))
                            time_seconds = (total_length / 1000) / 50 * 3600  # Assume 50 km/h
                    
                    if time_seconds <= travel_time_minutes * 60:
                        travel_times[node] = time_seconds
                except (nx.NetworkXNoPath, KeyError):
                    continue
            
            if not travel_times:
                return self._create_circular_buffer(center_point, travel_time_minutes, transport_mode)
            
            # Create convex hull of accessible nodes
            accessible_points = [
                Point(G.nodes[node]['x'], G.nodes[node]['y']) 
                for node in travel_times.keys()
            ]
            
            if len(accessible_points) < 3:
                return self._create_circular_buffer(center_point, travel_time_minutes, transport_mode)
            
            # Create buffer around accessible area
            accessible_area = unary_union(accessible_points)
            isochrone = accessible_area.convex_hull.buffer(0.001)  # Small buffer for smoothness
            
            return isochrone
            
        except Exception as e:
            logger.error(f"Error calculating isochrone: {e}")
            return self._create_circular_buffer(center_point, travel_time_minutes, transport_mode)
    
    def _create_circular_buffer(self, 
                               center_point: Tuple[float, float],
                               travel_time_minutes: float,
                               transport_mode: str) -> Polygon:
        """
        Create a simple circular buffer as fallback
        
        Args:
            center_point: (latitude, longitude)
            travel_time_minutes: Travel time in minutes
            transport_mode: Transport mode
            
        Returns:
            Circular Polygon
        """
        # Estimate distance based on transport mode
        speeds = {
            "walking": 5,  # km/h
            "transit": 30,  # km/h
            "driving": 50  # km/h
        }
        
        speed_kmh = speeds.get(transport_mode, 30)
        distance_km = (travel_time_minutes / 60) * speed_kmh
        distance_m = distance_km * 1000
        
        # Create circular buffer
        point = Point(center_point[1], center_point[0])  # Note: lon, lat for Shapely
        buffer = point.buffer(distance_m / 111320)  # Convert meters to degrees (rough)
        
        return buffer
    
    def calculate_commute_circle(self,
                                work_address: str,
                                commute_threshold_minutes: float,
                                transport_modes: List[str] = None) -> Dict[str, Polygon]:
        """
        Calculate commute circles for different transport modes
        
        Args:
            work_address: Address of workplace
            commute_threshold_minutes: Maximum acceptable commute time
            transport_modes: List of transport modes to calculate
            
        Returns:
            Dictionary mapping transport mode to isochrone polygon
        """
        if transport_modes is None:
            transport_modes = ["driving", "walking", "transit"]
        
        logger.info(f"Calculating commute circles for {work_address}")
        work_location = self.geocode_address(work_address)
        
        commute_circles = {}
        for mode in transport_modes:
            logger.info(f"Calculating {mode} isochrone...")
            isochrone = self.calculate_isochrone(
                work_location,
                commute_threshold_minutes,
                transport_mode=mode
            )
            commute_circles[mode] = isochrone
        
        return commute_circles
    
    def calculate_life_circle(self,
                             center_address: str,
                             life_threshold_minutes: float = 15,
                             transport_mode: str = "walking") -> Polygon:
        """
        Calculate life accessibility circle (typically walking distance to amenities)
        
        Args:
            center_address: Address of property or area center
            life_threshold_minutes: Maximum walking time to amenities
            transport_mode: Usually 'walking' for life circle
            
        Returns:
            Isochrone polygon for life accessibility
        """
        logger.info(f"Calculating life circle for {center_address}")
        center_location = self.geocode_address(center_address)
        
        isochrone = self.calculate_isochrone(
            center_location,
            life_threshold_minutes,
            transport_mode=transport_mode
        )
        
        return isochrone
    
    def check_point_in_circle(self, point: Tuple[float, float], 
                             circle: Polygon) -> bool:
        """
        Check if a point is within a geo-circle
        
        Args:
            point: (latitude, longitude)
            circle: Shapely Polygon representing the circle
            
        Returns:
            True if point is within circle
        """
        point_geom = Point(point[1], point[0])  # Note: lon, lat for Shapely
        return circle.contains(point_geom) or circle.touches(point_geom)
