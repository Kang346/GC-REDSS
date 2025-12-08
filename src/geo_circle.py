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
    
    def get_road_network(self, 
                        center_point: Tuple[float, float], 
                        distance: float = 5000,
                        transport_mode: str = "all") -> nx.MultiDiGraph:
        """
        Download and cache road network from OpenStreetMap based on transport mode
        
        Args:
            center_point: (latitude, longitude) center point
            distance: Distance in meters to extend network
            transport_mode: 'driving', 'walking', 'transit', 'biking', or 'all'
            
        Returns:
            NetworkX graph of road network
        """
        # Map transport mode to OSMnx network type
        network_type_map = {
            "driving": "drive",    # Only drivable roads
            "walking": "walk",     # Only walkable paths (includes sidewalks, pedestrian paths)
            "transit": "drive",    # Use drivable roads for transit (buses use roads)
            "biking": "bike",      # Only bikeable paths (includes bike lanes, bike paths)
            "all": "all"           # All road types
        }
        
        network_type = network_type_map.get(transport_mode, "all")
        
        # Include transport mode in cache key to separate different networks
        cache_key = f"{center_point[0]:.4f}_{center_point[1]:.4f}_{distance}_{network_type}"
        
        if cache_key in self.graph_cache:
            logger.info(f"Using cached {network_type} network for {cache_key}")
            return self.graph_cache[cache_key]
        
        try:
            logger.info(f"Downloading {network_type} road network for {center_point} (mode: {transport_mode})")
            G = ox.graph_from_point(
                center_point,
                dist=distance,
                network_type=network_type,
                simplify=True
            )
            
            # Add edge travel times based on speed limits and road types
            # Only add speeds/times for drivable networks
            if network_type in ["drive", "all"]:
                G = ox.add_edge_speeds(G)
                G = ox.add_edge_travel_times(G)
            else:
                # For walking networks, we'll calculate time based on length
                # No need to add speeds (walking speed is constant)
                pass
            
            self.graph_cache[cache_key] = G
            logger.info(f"{network_type.capitalize()} network downloaded: {len(G.nodes)} nodes, {len(G.edges)} edges")
            return G
            
        except Exception as e:
            logger.error(f"Error downloading {network_type} network: {e}")
            # Fallback to simple distance-based calculation
            return None
    
    def calculate_isochrone(self, 
                           center_point: Tuple[float, float],
                           travel_time_minutes: float,
                           transport_mode: str = "driving") -> Polygon:
        """
        Calculate isochrone polygon for given travel time using mode-specific network
        Optimized: Limits download range to 100km and uses batch shortest path algorithm
        
        Args:
            center_point: (latitude, longitude) starting point
            travel_time_minutes: Maximum travel time in minutes
            transport_mode: 'driving', 'walking', 'transit', or 'biking'
            
        Returns:
            Shapely Polygon representing the isochrone
        """
        try:
            # Estimate distance needed based on transport mode
            mode_speeds = {
                "driving": 50,   # km/h
                "walking": 5,    # km/h
                "transit": 30,   # km/h
                "biking": 15     # km/h (average cycling speed in urban areas)
            }
            speed_kmh = mode_speeds.get(transport_mode, 30)
            distance_km = (travel_time_minutes / 60) * speed_kmh
            distance_m = distance_km * 1000
            
            # LIMIT download range to maximum 100km to prevent downloading huge networks
            MAX_DOWNLOAD_DISTANCE = 100000  # meters (100km)
            download_distance = min(distance_m * 1.5, MAX_DOWNLOAD_DISTANCE)  # 1.5x buffer, max 100km
            
            logger.info(f"Downloading {transport_mode} network within {download_distance/1000:.1f}km radius (max 100km)")
            
            # Get mode-specific road network with limited range
            G = self.get_road_network(
                center_point, 
                distance=download_distance,
                transport_mode=transport_mode
            )
            
            if G is None:
                logger.warning(f"Using fallback circular buffer for {transport_mode}")
                return self._create_circular_buffer(center_point, travel_time_minutes, transport_mode)
            
            logger.info(f"Network loaded: {len(G.nodes)} nodes, {len(G.edges)} edges")
            
            # Find nearest node to center point
            center_node = ox.distance.nearest_nodes(G, center_point[1], center_point[0])
            
            # Calculate maximum travel time in seconds
            max_time_seconds = travel_time_minutes * 60
            
            # OPTIMIZED: Use batch shortest path algorithm (Dijkstra) instead of iterating all nodes
            # This calculates all shortest paths from center_node at once, much faster than looping
            travel_times = {}
            
            if transport_mode == "driving":
                # For driving: use travel_time weight if available
                try:
                    # Use single_source_dijkstra_path_length for batch calculation
                    # This calculates all shortest paths from center_node at once
                    # cutoff parameter limits search to nodes within max_time_seconds
                    path_lengths = nx.single_source_dijkstra_path_length(
                        G, center_node, weight='travel_time', cutoff=max_time_seconds
                    )
                    travel_times = {node: length for node, length in path_lengths.items()}
                except (KeyError, nx.NetworkXError):
                    # Fallback: use length and convert to time
                    # Estimate max distance for cutoff (50 km/h * max_time)
                    max_distance_m = (max_time_seconds / 3600) * 50 * 1000
                    path_lengths = nx.single_source_dijkstra_path_length(
                        G, center_node, weight='length', cutoff=max_distance_m
                    )
                    for node, length_m in path_lengths.items():
                        time_seconds = (length_m / 1000) / 50 * 3600
                        if time_seconds <= max_time_seconds:
                            travel_times[node] = time_seconds
                            
            elif transport_mode == "walking":
                # For walking: use length and convert to time
                # Estimate max distance for cutoff (5 km/h * max_time)
                max_distance_m = (max_time_seconds / 3600) * 5 * 1000
                path_lengths = nx.single_source_dijkstra_path_length(
                    G, center_node, weight='length', cutoff=max_distance_m
                )
                for node, length_m in path_lengths.items():
                    time_seconds = (length_m / 1000) / 5 * 3600
                    if time_seconds <= max_time_seconds:
                        travel_times[node] = time_seconds
                        
            elif transport_mode == "transit":
                # For transit: use length and convert to time
                # Estimate max distance for cutoff (30 km/h * max_time)
                max_distance_m = (max_time_seconds / 3600) * 30 * 1000
                path_lengths = nx.single_source_dijkstra_path_length(
                    G, center_node, weight='length', cutoff=max_distance_m
                )
                for node, length_m in path_lengths.items():
                    time_seconds = (length_m / 1000) / 30 * 3600
                    if time_seconds <= max_time_seconds:
                        travel_times[node] = time_seconds
                        
            elif transport_mode == "biking":
                # For biking: use length and convert to time
                # Estimate max distance for cutoff (15 km/h * max_time)
                max_distance_m = (max_time_seconds / 3600) * 15 * 1000
                path_lengths = nx.single_source_dijkstra_path_length(
                    G, center_node, weight='length', cutoff=max_distance_m
                )
                for node, length_m in path_lengths.items():
                    time_seconds = (length_m / 1000) / 15 * 3600
                    if time_seconds <= max_time_seconds:
                        travel_times[node] = time_seconds
            
            if not travel_times:
                logger.warning(f"No reachable nodes found for {transport_mode}, using fallback")
                return self._create_circular_buffer(center_point, travel_time_minutes, transport_mode)
            
            # Create convex hull of accessible nodes
            accessible_points = [
                Point(G.nodes[node]['x'], G.nodes[node]['y']) 
                for node in travel_times.keys()
            ]
            
            if len(accessible_points) < 3:
                logger.warning(f"Too few accessible points for {transport_mode}, using fallback")
                return self._create_circular_buffer(center_point, travel_time_minutes, transport_mode)
            
            # Create buffer around accessible area
            accessible_area = unary_union(accessible_points)
            isochrone = accessible_area.convex_hull.buffer(0.001)  # Small buffer for smoothness
            
            logger.info(f"{transport_mode.capitalize()} isochrone calculated: {len(travel_times)} reachable nodes")
            return isochrone
            
        except Exception as e:
            logger.error(f"Error calculating {transport_mode} isochrone: {e}")
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
            "driving": 50,  # km/h
            "biking": 15   # km/h (average urban cycling speed)
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
        Each mode uses its own specific road network
        
        Args:
            work_address: Address of workplace
            commute_threshold_minutes: Maximum acceptable commute time
            transport_modes: List of transport modes to calculate
            
        Returns:
            Dictionary mapping transport mode to isochrone polygon
        """
        if transport_modes is None:
            transport_modes = ["driving", "walking", "transit", "biking"]
        
        logger.info(f"Calculating commute circles for {work_address} with modes: {transport_modes}")
        work_location = self.geocode_address(work_address)
        
        commute_circles = {}
        for mode in transport_modes:
            logger.info(f"Calculating {mode} isochrone with {mode}-specific network...")
            isochrone = self.calculate_isochrone(
                work_location,
                commute_threshold_minutes,
                transport_mode=mode
            )
            commute_circles[mode] = isochrone
            logger.info(f"{mode.capitalize()} commute circle calculated successfully")
        
        return commute_circles
    
    def calculate_life_circle(self,
                             center_address: str,
                             life_threshold_minutes: float = 15,
                             transport_mode: str = "walking") -> Polygon:
        """
        Calculate life accessibility circle (typically walking distance to amenities)
        Uses walking-specific network (includes sidewalks, pedestrian paths)
        
        Args:
            center_address: Address of property or area center
            life_threshold_minutes: Maximum walking time to amenities
            transport_mode: Usually 'walking' for life circle
            
        Returns:
            Isochrone polygon for life accessibility
        """
        logger.info(f"Calculating life circle for {center_address} using {transport_mode} network")
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
