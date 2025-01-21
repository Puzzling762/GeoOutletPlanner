import requests
import networkx as nx
from geopy.distance import geodesic
import logging
from shapely.geometry import LineString

logger = logging.getLogger(__name__)
OSRM_CACHE = {}  # Cache for OSRM routes to reduce redundant API calls

def get_osrm_route(start, end):
    """
    Fetch a route from OSRM between two points.
    Cache results to minimize redundant requests.
    """
    global OSRM_CACHE
    route_key = (start, end)
    if route_key in OSRM_CACHE:
        return OSRM_CACHE[route_key]
    
    url = f"https://router.project-osrm.org/route/v1/driving/{start[1]},{start[0]};{end[1]},{end[0]}?overview=full&geometries=geojson"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if "routes" in data and len(data["routes"]) > 0:
            geometry = data["routes"][0]["geometry"]
            OSRM_CACHE[route_key] = geometry  # Cache the result
            return geometry
        else:
            logger.warning(f"No route found between {start} and {end}")
            return None
    except requests.RequestException as e:
        logger.error(f"Error fetching OSRM route: {e}")
        return None

def calculate_road_distance(graph, lat1, lon1, lat2, lon2):
    """
    Calculate the shortest road distance between two locations using the OSRM graph.
    """
    try:
        node1 = find_nearest_node(graph, lat1, lon1)
        node2 = find_nearest_node(graph, lat2, lon2)

        if node1 and node2:
            return nx.shortest_path_length(graph, node1, node2, weight="weight")
        else:
            logger.warning("Falling back to geodesic distance.")
            return geodesic((lat1, lon1), (lat2, lon2)).km
    except Exception as e:
        logger.error(f"Error calculating road distance: {e}")
        return geodesic((lat1, lon1), (lat2, lon2)).km

def load_graph_from_osrm_route(min_lat, min_lon, max_lat, max_lon):
    """
    Create a road network graph for a bounding box using OSRM.
    """
    try:
        G = nx.Graph()
        start = (min_lat, min_lon)
        end = (max_lat, max_lon)
        geometry = get_osrm_route(start, end)

        if geometry:
            coords = geometry["coordinates"]
            for i in range(len(coords) - 1):
                point1 = tuple(coords[i])
                point2 = tuple(coords[i + 1])
                distance = geodesic((point1[1], point1[0]), (point2[1], point2[0])).km
                G.add_edge(point1, point2, weight=distance)
            return G
        else:
            logger.error("Failed to load road network from OSRM.")
            return None
    except Exception as e:
        logger.error(f"Unexpected error in graph creation: {e}")
        return None

def find_nearest_node(graph, lat, lon):
    """
    Find the nearest node in the road graph to the given latitude and longitude.
    """
    try:
        nearest_node = min(
            graph.nodes,
            key=lambda node: geodesic((lat, lon), (node[1], node[0])).km,
            default=None,
        )
        return nearest_node
    except Exception as e:
        logger.error(f"Error finding nearest node: {e}")
        return None
