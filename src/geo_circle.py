"""
Geo-Circle (Isochrone) calculation module for commute and life accessibility zones
"""
import osmnx as ox
import networkx as nx
import numpy as np
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from shapely.geometry import Point, Polygon, LineString
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
            "subway": "drive",     # Subway uses same network (we'll handle subway stations separately)
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
            logger.info(f"  This may take 1-3 minutes depending on network size and internet speed...")
            # Force output flush to show progress immediately
            import sys
            sys.stdout.flush()
            G = ox.graph_from_point(
                center_point,
                dist=distance,
                network_type=network_type,
                simplify=True
            )
            logger.info(f"  ✓ Network download completed, processing...")
            sys.stdout.flush()
            
            # Add edge travel times based on speed limits and road types
            # Only add speeds/times for drivable networks
            if network_type in ["drive", "all"]:
                G = ox.add_edge_speeds(G)
                G = ox.add_edge_travel_times(G)
                
                # Override travel times for highways (use 15 km/h instead of default speeds)
                # This ensures highways are faster than regular streets (10 km/h)
                if transport_mode == "driving":
                    HIGHWAY_TYPES = ['motorway', 'motorway_link', 'trunk', 'trunk_link', 
                                   'primary', 'primary_link', 'secondary', 'secondary_link']
                    for u, v, key, data in G.edges(keys=True, data=True):
                        highway_type = data.get('highway', '')
                        if isinstance(highway_type, list):
                            highway_type = highway_type[0] if highway_type else ''
                        
                        # Check if this is a highway
                        is_highway = any(ht in str(highway_type) for ht in HIGHWAY_TYPES)
                        
                        if is_highway and 'length' in data:
                            # Override speed for highways: 15 km/h
                            length_m = data['length']
                            speed_ms = 15 / 3.6  # Convert km/h to m/s
                            travel_time_s = length_m / speed_ms
                            data['speed_kph'] = 15
                            data['travel_time'] = travel_time_s
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
            # Realistic speeds for Manhattan urban areas (reduced)
            mode_speeds = {
                "driving": 10,   # km/h (Manhattan average is 8-10 km/h due to heavy traffic)
                "walking": 3.3,  # km/h (reduced proportionally: 4 * 10/12)
                "transit": 8.3,  # km/h (reduced proportionally: 10 * 10/12, buses are very slow)
                "biking": 8.3,   # km/h (reduced proportionally: 10 * 10/12)
                "subway": 25,    # km/h (subway average speed in Manhattan, including stops)
            }
            speed_kmh = mode_speeds.get(transport_mode, 30)
            distance_km = (travel_time_minutes / 60) * speed_kmh
            distance_m = distance_km * 1000
            
            # IMPORTANT: Download range must be large enough to cover all reachable areas
            # Even with slow speeds, we need to download a large enough network to ensure
            # all areas within time limit are included (especially for irregular road networks)
            # For 30min at 12km/h = 6km, but we need larger network to find all paths
            MAX_DOWNLOAD_DISTANCE = 30000  # meters (30km - enough for Manhattan area)
            # Use larger buffer (1.5x) to ensure we capture all possible routes
            download_distance = min(distance_m * 1.5, MAX_DOWNLOAD_DISTANCE)  # 1.5x buffer, max 30km
            
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
            
            # Find nearest node to center point - improved accuracy
            try:
                center_node = ox.distance.nearest_nodes(G, center_point[1], center_point[0])
                # Log for debugging
                center_node_coords = (G.nodes[center_node].get('y', 0), G.nodes[center_node].get('x', 0))
                dist_from_start = geodesic(center_point, center_node_coords).meters
                logger.info(f"Center node: {center_node}, distance from start: {dist_from_start:.0f}m")
            except Exception as e:
                logger.error(f"Error finding center node: {e}")
                # Fallback: find closest node manually
                min_dist = float('inf')
                center_node = None
                for node in G.nodes():
                    node_lat = G.nodes[node].get('y', 0)
                    node_lon = G.nodes[node].get('x', 0)
                    dist = geodesic(center_point, (node_lat, node_lon)).meters
                    if dist < min_dist:
                        min_dist = dist
                        center_node = node
                if center_node is None:
                    logger.error("Could not find any node in graph")
                    return self._create_circular_buffer(center_point, travel_time_minutes, transport_mode)
                logger.info(f"Using fallback center node: {center_node}, distance: {min_dist:.0f}m")
            
            # Calculate maximum travel time in seconds
            max_time_seconds = travel_time_minutes * 60
            
            logger.info(f"Calculating shortest paths from center node (this may take 30-60 seconds)...")
            import sys
            sys.stdout.flush()
            # OPTIMIZED: Use batch shortest path algorithm (Dijkstra) instead of iterating all nodes
            # This calculates all shortest paths from center_node at once, much faster than looping
            travel_times = {}
            
            if transport_mode == "driving":
                # For driving: use travel_time weight if available
                try:
                    # Use single_source_dijkstra_path_length for batch calculation
                    # IMPORTANT: Use larger cutoff (1.2x) to ensure all reachable nodes are found
                    # This prevents missing areas due to cutoff being too strict
                    cutoff_with_buffer = max_time_seconds * 1.2  # 1.2x buffer
                    path_lengths = nx.single_source_dijkstra_path_length(
                        G, center_node, weight='travel_time', cutoff=cutoff_with_buffer
                    )
                    # Filter to only include nodes within actual time limit
                    travel_times = {node: length for node, length in path_lengths.items() 
                                   if length <= max_time_seconds}
                except (KeyError, nx.NetworkXError):
                    # Fallback: use length and convert to time with highway detection
                    # IMPORTANT: Use larger cutoff (1.3x buffer) to ensure all reachable nodes are found
                    # This prevents missing areas that are reachable but slightly further due to road network
                    base_distance_m = (max_time_seconds / 3600) * 10 * 1000  # 10 km/h base speed
                    max_distance_m = base_distance_m * 1.3  # 1.3x buffer to catch all reachable areas
                    path_lengths = nx.single_source_dijkstra_path_length(
                        G, center_node, weight='length', cutoff=max_distance_m
                    )
                    
                    # Calculate travel time with highway speed differentiation
                    for node, length_m in path_lengths.items():
                        # For now, use average speed (will be refined with actual path)
                        # Regular streets: 10 km/h, Highways: 15 km/h
                        # We'll use weighted average: assume 30% highways, 70% regular streets
                        avg_speed_kmh = 10 * 0.7 + 15 * 0.3  # ~11.5 km/h average
                        time_seconds = (length_m / 1000) / avg_speed_kmh * 3600
                        if time_seconds <= max_time_seconds:
                            travel_times[node] = time_seconds
                            
            elif transport_mode == "walking":
                # For walking: use length and convert to time
                # Use larger cutoff (1.3x buffer) to ensure all reachable nodes are found
                base_distance_m = (max_time_seconds / 3600) * 3.3 * 1000  # 3.3 km/h
                max_distance_m = base_distance_m * 1.3  # 1.3x buffer
                path_lengths = nx.single_source_dijkstra_path_length(
                    G, center_node, weight='length', cutoff=max_distance_m
                )
                for node, length_m in path_lengths.items():
                    time_seconds = (length_m / 1000) / 3.3 * 3600
                    if time_seconds <= max_time_seconds:
                        travel_times[node] = time_seconds
                        
            elif transport_mode == "transit":
                # For transit: use length and convert to time
                # Use larger cutoff (1.3x buffer) to ensure all reachable nodes are found
                base_distance_m = (max_time_seconds / 3600) * 8.3 * 1000  # 8.3 km/h
                max_distance_m = base_distance_m * 1.3  # 1.3x buffer
                path_lengths = nx.single_source_dijkstra_path_length(
                    G, center_node, weight='length', cutoff=max_distance_m
                )
                for node, length_m in path_lengths.items():
                    time_seconds = (length_m / 1000) / 8.3 * 3600
                    if time_seconds <= max_time_seconds:
                        travel_times[node] = time_seconds
                        
            elif transport_mode == "biking":
                # For biking: use length and convert to time
                # Use larger cutoff (1.3x buffer) to ensure all reachable nodes are found
                base_distance_m = (max_time_seconds / 3600) * 8.3 * 1000  # 8.3 km/h
                max_distance_m = base_distance_m * 1.3  # 1.3x buffer
                path_lengths = nx.single_source_dijkstra_path_length(
                    G, center_node, weight='length', cutoff=max_distance_m
                )
                for node, length_m in path_lengths.items():
                    time_seconds = (length_m / 1000) / 8.3 * 3600
                    if time_seconds <= max_time_seconds:
                        travel_times[node] = time_seconds
                        
            elif transport_mode == "subway":
                # For subway: use length and convert to time (25 km/h average subway speed)
                # Subway is faster but has stops, so average speed is lower than top speed
                base_distance_m = (max_time_seconds / 3600) * 25 * 1000  # 25 km/h
                max_distance_m = base_distance_m * 1.3  # 1.3x buffer
                path_lengths = nx.single_source_dijkstra_path_length(
                    G, center_node, weight='length', cutoff=max_distance_m
                )
                for node, length_m in path_lengths.items():
                    time_seconds = (length_m / 1000) / 25 * 3600
                    if time_seconds <= max_time_seconds:
                        travel_times[node] = time_seconds
            
            if not travel_times:
                logger.warning(f"No reachable nodes found for {transport_mode}, using fallback")
                return self._create_circular_buffer(center_point, travel_time_minutes, transport_mode)
            
            # IMPROVED: Create irregular isochrone based on actual road network edges
            # Strategy: Use both edges AND nodes to ensure complete coverage in all directions
            # This ensures that even if edge collection is limited, all reachable areas are included
            
            logger.info("Creating irregular isochrone from road network...")
            logger.info(f"Total reachable nodes: {len(travel_times)}")
            
            # Step 1: Collect accessible edges (prioritize edges connected to reachable nodes)
            accessible_edges = []
            edge_count = 0
            MAX_EDGES = 15000  # Increased limit for better coverage
            
            # First, collect edges connected to reachable nodes (ensures all directions)
            reachable_node_set = set(travel_times.keys())
            
            for u, v, data in G.edges(data=True):
                if edge_count >= MAX_EDGES:
                    break
                    
                # Check if either endpoint is reachable
                if u in reachable_node_set or v in reachable_node_set:
                    # Get edge geometry if available
                    if 'geometry' in data:
                        accessible_edges.append(data['geometry'])
                    else:
                        # Create line from node coordinates
                        u_coords = (G.nodes[u]['x'], G.nodes[u]['y'])
                        v_coords = (G.nodes[v]['x'], G.nodes[v]['y'])
                        accessible_edges.append(LineString([u_coords, v_coords]))
                    edge_count += 1
            
            logger.info(f"Collected {len(accessible_edges)} accessible edges")
            
            # Step 2: Create isochrone from edges + nodes (hybrid approach for complete coverage)
            if accessible_edges:
                try:
                    # Union all accessible edges
                    edges_union = unary_union(accessible_edges)
                    
                    # Buffer size based on transport mode (proportional to speed)
                    # Reduced buffers since speeds are lower and distances are shorter
                    buffer_sizes = {
                        "driving": 0.002,    # ~200m buffer (reduced - shorter distances need smaller buffers)
                        "walking": 0.001,   # ~100m buffer
                        "transit": 0.0015,   # ~150m buffer
                        "biking": 0.0015,   # ~150m buffer
                    }
                    buffer_size = buffer_sizes.get(transport_mode, 0.002)
                    
                    # Create buffer around edges
                    edges_buffered = edges_union.buffer(buffer_size)
                    
                    # Also create buffer around reachable nodes to fill any gaps
                    accessible_points = [
                        Point(G.nodes[node]['x'], G.nodes[node]['y']) 
                        for node in list(travel_times.keys())[:5000]  # Limit nodes for performance
                    ]
                    if accessible_points:
                        points_union = unary_union(accessible_points)
                        points_buffered = points_union.buffer(buffer_size * 0.5)  # Smaller buffer for points
                        
                        # Combine edges and points buffers
                        isochrone = unary_union([edges_buffered, points_buffered])
                    else:
                        isochrone = edges_buffered
                    
                except Exception as e:
                    logger.warning(f"Edge union failed, using node-based fallback: {e}")
                    # Fallback to node-based
                    accessible_points = [
                        Point(G.nodes[node]['x'], G.nodes[node]['y']) 
                        for node in travel_times.keys()
                    ]
                    if len(accessible_points) < 3:
                        return self._create_circular_buffer(center_point, travel_time_minutes, transport_mode)
                    accessible_area = unary_union(accessible_points)
                    buffer_size = 0.002 if transport_mode == "driving" else 0.001
                    isochrone = accessible_area.buffer(buffer_size)
            else:
                # Fallback: use accessible nodes with larger buffer
                logger.warning("No accessible edges found, using nodes as fallback")
                accessible_points = [
                    Point(G.nodes[node]['x'], G.nodes[node]['y']) 
                    for node in travel_times.keys()
                ]
                if len(accessible_points) < 3:
                    return self._create_circular_buffer(center_point, travel_time_minutes, transport_mode)
                accessible_area = unary_union(accessible_points)
                # Use proportional buffer (smaller since speeds are lower)
                buffer_size = 0.002 if transport_mode == "driving" else 0.001
                isochrone = accessible_area.buffer(buffer_size)
            
            # Ensure it's a valid polygon
            if not isinstance(isochrone, Polygon):
                if hasattr(isochrone, 'geoms'):
                    # If it's a MultiPolygon, take the largest one (or union all if they're close)
                    if len(isochrone.geoms) == 1:
                        isochrone = isochrone.geoms[0]
                    else:
                        # If multiple polygons, take the largest one (main area)
                        # This handles cases where there might be disconnected small areas
                        isochrone = max(isochrone.geoms, key=lambda p: p.area)
                elif hasattr(isochrone, 'buffer'):
                    # Try to fix invalid geometry
                    try:
                        isochrone = isochrone.buffer(0)
                    except:
                        # Final fallback
                        accessible_points = [
                            Point(G.nodes[node]['x'], G.nodes[node]['y']) 
                            for node in list(travel_times.keys())[:1000]
                        ]
                        accessible_area = unary_union(accessible_points)
                        isochrone = accessible_area.buffer(0.002)  # Reduced buffer
            
            # Validate the polygon
            if not isochrone.is_valid:
                try:
                    isochrone = isochrone.buffer(0)  # Fix self-intersections
                except:
                    logger.warning("Could not fix invalid polygon geometry")
            
            logger.info(f"{transport_mode.capitalize()} irregular isochrone calculated: {len(travel_times)} reachable nodes, {len(accessible_edges)} accessible edges")
            logger.info(f"Isochrone area: {isochrone.area:.6f} square degrees (~{isochrone.area * 111 * 111:.1f} km²)")
            return isochrone
            
        except Exception as e:
            logger.error(f"Error calculating {transport_mode} isochrone: {e}")
            return self._create_circular_buffer(center_point, travel_time_minutes, transport_mode)
    
    def calculate_isochrone_fast(self,
                                center_point: Tuple[float, float],
                                travel_time_minutes: float,
                                transport_mode: str = "driving") -> Polygon:
        """
        Fast version of isochrone calculation using smaller network
        Still based on actual road network, but with limited range for speed
        
        Args:
            center_point: (latitude, longitude) starting point
            travel_time_minutes: Maximum travel time in minutes
            transport_mode: 'driving', 'walking', 'transit', or 'biking'
            
        Returns:
            Shapely Polygon representing the isochrone (irregular shape based on roads)
        """
        try:
            # Estimate distance needed (more conservative for fast mode)
            mode_speeds = {
                "driving": 10,   # km/h (Manhattan speed, reduced)
                "walking": 3.3,  # km/h (reduced proportionally)
                "transit": 8.3,  # km/h (reduced proportionally)
                "biking": 8.3,   # km/h (reduced proportionally)
                "subway": 25,    # km/h (subway average speed)
            }
            speed_kmh = mode_speeds.get(transport_mode, 12)
            distance_km = (travel_time_minutes / 60) * speed_kmh
            # Calculate actual needed distance
            # IMPORTANT: Use larger buffer to ensure all reachable areas are included
            actual_distance_m = distance_km * 1000
            # For 30min at 12km/h = 6km, but we need larger network to find all paths
            # Use larger max distance to ensure coverage of Manhattan area
            FAST_MODE_MAX_DISTANCE = min(actual_distance_m * 2.0, 25000)  # Max 25km (increased for better coverage)
            distance_m = min(actual_distance_m * 1.5, FAST_MODE_MAX_DISTANCE)  # 1.5x buffer, max 25km
            
            logger.info(f"Fast mode: Downloading {transport_mode} network within {distance_m/1000:.1f}km radius")
            
            # Get road network (smaller range for speed)
            G = self.get_road_network(
                center_point, 
                distance=distance_m,
                transport_mode=transport_mode
            )
            
            if G is None or len(G.nodes) == 0:
                logger.warning(f"Fast mode: Network unavailable, using circular fallback")
                return self._create_circular_buffer(center_point, travel_time_minutes, transport_mode)
            
            # Find nearest node - use multiple methods for better accuracy
            min_dist = None
            try:
                center_node = ox.distance.nearest_nodes(G, center_point[1], center_point[0])
                # Verify the node is actually in the graph and calculate distance
                if center_node in G.nodes:
                    center_node_coords = (G.nodes[center_node].get('y', 0), G.nodes[center_node].get('x', 0))
                    min_dist = geodesic(center_point, center_node_coords).meters
                    logger.info(f"Using center node: {center_node} (distance from start: {min_dist:.0f}m)")
                else:
                    logger.warning(f"Nearest node {center_node} not in graph, finding alternative")
                    # Find closest node by distance
                    min_dist = float('inf')
                    center_node = None
                    for node in G.nodes():
                        node_lat = G.nodes[node].get('y', 0)
                        node_lon = G.nodes[node].get('x', 0)
                        dist = geodesic(center_point, (node_lat, node_lon)).meters
                        if dist < min_dist:
                            min_dist = dist
                            center_node = node
                    if center_node:
                        logger.info(f"Using alternative center node: {center_node} (distance: {min_dist:.0f}m)")
            except Exception as e:
                logger.error(f"Error finding center node: {e}")
                # Fallback: find closest node manually
                min_dist = float('inf')
                center_node = None
                for node in G.nodes():
                    node_lat = G.nodes[node].get('y', 0)
                    node_lon = G.nodes[node].get('x', 0)
                    dist = geodesic(center_point, (node_lat, node_lon)).meters
                    if dist < min_dist:
                        min_dist = dist
                        center_node = node
                if center_node:
                    logger.info(f"Using fallback center node: {center_node} (distance: {min_dist:.0f}m)")
            
            if center_node is None:
                logger.error("Could not find center node in graph")
                return self._create_circular_buffer(center_point, travel_time_minutes, transport_mode)
            
            max_time_seconds = travel_time_minutes * 60
            
            # Calculate shortest paths (optimized for fast mode)
            # Use more aggressive cutoff to limit computation
            travel_times = {}
            if transport_mode == "driving":
                try:
                    # Use cutoff to limit search (faster)
                    path_lengths = nx.single_source_dijkstra_path_length(
                        G, center_node, weight='travel_time', cutoff=max_time_seconds
                    )
                    travel_times = {node: length for node, length in path_lengths.items()}
                except (KeyError, nx.NetworkXError):
                    # Distance cutoff (using Manhattan speed)
                    # IMPORTANT: Use larger cutoff to ensure all reachable nodes are found
                    max_distance_m = min((max_time_seconds / 3600) * 12 * 1000 * 1.2, FAST_MODE_MAX_DISTANCE)  # 1.2x buffer
                    path_lengths = nx.single_source_dijkstra_path_length(
                        G, center_node, weight='length', cutoff=max_distance_m
                    )
                    for node, length_m in path_lengths.items():
                        time_seconds = (length_m / 1000) / 10 * 3600  # 10 km/h for Manhattan driving
                        if time_seconds <= max_time_seconds:
                            travel_times[node] = time_seconds
            else:
                # For other modes, use length-based calculation with cutoff
                speed_kmh = mode_speeds.get(transport_mode, 30)
                max_distance_m = min((max_time_seconds / 3600) * speed_kmh * 1000, FAST_MODE_MAX_DISTANCE)
                path_lengths = nx.single_source_dijkstra_path_length(
                    G, center_node, weight='length', cutoff=max_distance_m
                )
                for node, length_m in path_lengths.items():
                    time_seconds = (length_m / 1000) / speed_kmh * 3600
                    if time_seconds <= max_time_seconds:
                        travel_times[node] = time_seconds
            
            if not travel_times:
                return self._create_circular_buffer(center_point, travel_time_minutes, transport_mode)
            
            # FAST MODE: Optimized for speed - use simplified approach
            # Limit processing to ensure fast response (< 30 seconds)
            accessible_edges = []
            reachable_node_set = set(travel_times.keys())
            edge_count = 0
            MAX_EDGES_FAST_MODE = 5000  # Reduced for faster processing
            MAX_NODES_FAST_MODE = 2000  # Limit nodes for faster union operations
            
            # Collect edges connected to reachable nodes
            for u, v, data in G.edges(data=True):
                if edge_count >= MAX_EDGES_FAST_MODE:
                    break
                    
                if u in reachable_node_set or v in reachable_node_set:
                    if 'geometry' in data:
                        accessible_edges.append(data['geometry'])
                    else:
                        u_coords = (G.nodes[u]['x'], G.nodes[u]['y'])
                        v_coords = (G.nodes[v]['x'], G.nodes[v]['y'])
                        accessible_edges.append(LineString([u_coords, v_coords]))
                    edge_count += 1
            
            if accessible_edges:
                try:
                    # FAST MODE: Use simplified approach - limit edges for speed
                    # Only process first 1000 edges to ensure fast union operation
                    edges_to_process = accessible_edges[:1000]
                    edges_union = unary_union(edges_to_process)
                    buffer_sizes = {
                        "driving": 0.0015,    # ~150m buffer (further reduced for shorter distances)
                        "walking": 0.0008,   # ~80m buffer
                        "transit": 0.0012,   # ~120m buffer
                        "biking": 0.0012,   # ~120m buffer
                    }
                    buffer_size = buffer_sizes.get(transport_mode, 0.0015)
                    edges_buffered = edges_union.buffer(buffer_size)
                    
                    # Use limited nodes for faster processing
                    node_list = list(travel_times.keys())[:MAX_NODES_FAST_MODE]
                    if node_list:
                        accessible_points = [
                            Point(G.nodes[node]['x'], G.nodes[node]['y']) 
                            for node in node_list
                        ]
                        points_union = unary_union(accessible_points)
                        points_buffered = points_union.buffer(buffer_size * 0.3)  # Smaller buffer for points
                        isochrone = unary_union([edges_buffered, points_buffered])
                    else:
                        isochrone = edges_buffered
                    
                    # Validate polygon (quick check)
                    if not isinstance(isochrone, Polygon):
                        if hasattr(isochrone, 'geoms'):
                            isochrone = max(isochrone.geoms, key=lambda p: p.area)
                    
                    # Skip expensive validation in fast mode
                    return isochrone
                except Exception as e:
                    logger.warning(f"Fast mode edge union failed: {e}")
                    # Fall through to simplified node-based fallback
            
            # Fallback to simplified node-based (fast)
            node_list = list(travel_times.keys())[:MAX_NODES_FAST_MODE]
            if len(node_list) >= 3:
                accessible_points = [
                    Point(G.nodes[node]['x'], G.nodes[node]['y']) 
                    for node in node_list
                ]
                accessible_area = unary_union(accessible_points)
                buffer_size = 0.0015 if transport_mode == "driving" else 0.0008  # Further reduced
                isochrone = accessible_area.buffer(buffer_size)
                return isochrone
            else:
                return self._create_circular_buffer(center_point, travel_time_minutes, transport_mode)
                    
        except Exception as e:
            logger.error(f"Fast mode isochrone calculation error: {e}")
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
        # Estimate distance based on transport mode (Manhattan speeds, reduced)
        speeds = {
            "walking": 3.3,  # km/h (reduced proportionally)
            "transit": 8.3,  # km/h (reduced proportionally)
            "driving": 10,  # km/h (Manhattan average is 8-10 km/h)
            "biking": 8.3,   # km/h (reduced proportionally)
            "subway": 25,    # km/h (subway average speed)
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
                                transport_modes: List[str] = None,
                                fast_mode: bool = False) -> Dict[str, Polygon]:
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
        logger.info(f"✓ Work location geocoded: {work_location}")
        
        commute_circles = {}
        
        # FAST MODE: Use simplified road network calculation (faster, but still based on roads)
        if fast_mode:
            logger.info("⚡ FAST MODE: Using simplified road network calculation (response time: ~2-5 seconds)")
            logger.info("   - Downloads smaller road network (20km radius)")
            logger.info("   - Still uses actual road network for irregular shapes")
            for mode in transport_modes:
                try:
                    # Use smaller network for fast mode (20km instead of 100km)
                    # This is still based on actual roads, just a smaller area
                    isochrone = self.calculate_isochrone_fast(
                        work_location,
                        commute_threshold_minutes,
                        transport_mode=mode
                    )
                    commute_circles[mode] = isochrone
                except Exception as e:
                    logger.warning(f"Fast mode failed for {mode}, using circular fallback: {e}")
                    commute_circles[mode] = self._create_circular_buffer(
                        work_location,
                        commute_threshold_minutes,
                        mode
                    )
            logger.info("✓ Fast mode circles calculated (based on actual road network)")
            return commute_circles
        
        # FULL MODE: Use full road network calculation (slower, but more accurate)
        logger.info("=" * 80)
        logger.info("⚠️  FULL MODE: Downloading road network data from OpenStreetMap")
        logger.info("   - This may take 3-5 minutes (downloading network data)")
        logger.info("   - Subsequent runs will be faster (using cached data)")
        logger.info("=" * 80)
        
        total_modes = len(transport_modes)
        logger.info(f"\n📊 Processing {total_modes} transport mode(s)...")
        for idx, mode in enumerate(transport_modes, 1):
            logger.info(f"\n[{idx}/{total_modes}] 🚗 Processing {mode.upper()} mode...")
            logger.info(f"   Step {idx}.1: Downloading {mode} road network...")
            logger.info(f"   Step {idx}.2: Calculating shortest paths...")
            logger.info(f"   Step {idx}.3: Generating isochrone polygon...")
            try:
                isochrone = self.calculate_isochrone(
                    work_location,
                    commute_threshold_minutes,
                    transport_mode=mode
                )
                commute_circles[mode] = isochrone
                logger.info(f"   ✓ {mode.capitalize()} commute circle calculated successfully!")
            except Exception as e:
                logger.error(f"   ✗ Error calculating {mode} circle: {e}")
                logger.warning(f"   Using fallback for {mode} mode")
                commute_circles[mode] = self._create_circular_buffer(
                    work_location,
                    commute_threshold_minutes,
                    mode
                )
        logger.info(f"\n✅ All commute circles calculated!")
        
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
