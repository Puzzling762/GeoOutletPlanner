import json
import geopandas as gpd
from shapely.geometry import LineString
import logging
# In visualization.py
from osm_utils import get_osrm_route  # Correct the import source




def create_geodataframes(outlets, demand_centers):
    """
    Convert outlets and demand centers into GeoDataFrames.
    """
    demand_gdf = gpd.GeoDataFrame(
        demand_centers,
        geometry=gpd.points_from_xy(demand_centers['lon'], demand_centers['lat']),
        crs="EPSG:4326"
    )
    outlet_gdf = gpd.GeoDataFrame(
        outlets,
        geometry=gpd.points_from_xy(outlets['lon'], outlets['lat']),
        crs="EPSG:4326"
    )
    return demand_gdf, outlet_gdf


def create_connection_features(assignments, demand_gdf, outlet_gdf, road_graph):
    """
    Generate GeoJSON LineString features for connections between demand centers and outlets
    using OSRM road network.
    """
    connection_features = []

    for _, assignment in assignments.iterrows():
        demand_point = demand_gdf.loc[demand_gdf['id'] == assignment['demand_id'], 'geometry'].values[0]
        outlet_point = outlet_gdf.loc[outlet_gdf['id'] == assignment['outlet_id'], 'geometry'].values[0]
        
        start = (demand_point.y, demand_point.x)  # (lat, lon)
        end = (outlet_point.y, outlet_point.x)  # (lat, lon)
        
        route_geometry = get_osrm_route(start, end)
        
        if route_geometry:
            connection_features.append({
                'type': 'Feature',
                'geometry': LineString(route_geometry['coordinates']).__geo_interface__,
                'properties': {
                    'demand_id': assignment['demand_id'],
                    'outlet_id': assignment['outlet_id'],
                    'distance': assignment['distance']
                }
            })
        else:
            logging.warning(f"No route found between demand {assignment['demand_id']} and outlet {assignment['outlet_id']}")
            
    return connection_features


def visualize_map(outlets, demand_centers, assignments, road_graph, map_file_path):
    """
    Visualize the optimized retail map and save it as a GeoJSON file, 
    using OSRM roads to connect outlets and demand centers.
    """
    try:
        # Convert data into GeoDataFrames
        demand_gdf, outlet_gdf = create_geodataframes(outlets, demand_centers)

        # Generate features for GeoJSON
        features = []

        # Add demand center features with a common symbol
        features += [
            {
                'type': 'Feature',
                'geometry': row.geometry.__geo_interface__,
                'properties': {
                    'id': row['id'],
                    'type': 'demand',
                    'population': row['population'],
                    'marker-symbol': 'circle',  # Symbol for demand centers
                    'marker-color': '#FF0000',  # Red color for demand centers
                }
            }
            for _, row in demand_gdf.iterrows()
        ]

        # Add outlet features with unique symbols
        symbols = ['star', 'triangle', 'square', 'cross', 'diamond']  # List of unique symbols
        features += [
            {
                'type': 'Feature',
                'geometry': row.geometry.__geo_interface__,
                'properties': {
                    'id': row['id'],
                    'type': 'outlet',
                    'marker-symbol': symbols[int(row['id']) % len(symbols)],  # Assign a symbol based on ID
                    'marker-color': '#0000FF',  # Blue color for outlets
                }
            }
            for _, row in outlet_gdf.iterrows()
        ]

        # Add connection features using OSRM routes
        features += create_connection_features(assignments, demand_gdf, outlet_gdf, road_graph)

        # Construct GeoJSON
        geojson_data = {'type': 'FeatureCollection', 'features': features}

        # Save GeoJSON to file
        with open(map_file_path, 'w') as f:
            json.dump(geojson_data, f, indent=2)

    except Exception as e:
        raise RuntimeError(f"Error generating GeoJSON map: {e}")
