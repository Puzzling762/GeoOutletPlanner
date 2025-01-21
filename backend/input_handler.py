import pandas as pd
from osm_utils import find_nearest_node

def process_inputs(demand_centers, graph):
    """
    Process demand center data into a DataFrame and connect them to the road network.
    """
    # Convert demand_centers into a DataFrame
    df = pd.DataFrame(demand_centers).rename(columns={"latitude": "lat", "longitude": "lon"})

    # Ensure population column exists
    if 'population' not in df.columns:
        df['population'] = 1  # Default population if not provided

    # Connect demand centers to the road network
    connected_centers = []
    for _, row in df.iterrows():
        nearest_node = find_nearest_node(graph, row['lat'], row['lon'])
        if nearest_node:
            connected_centers.append({
                'id': row['id'],
                'lat': nearest_node[1],  # Graph uses (lon, lat) -> reverse to (lat, lon)
                'lon': nearest_node[0],
                'population': row['population']
            })
        else:
            # If no road connection, keep the demand center as-is
            connected_centers.append({
                'id': row['id'],
                'lat': row['lat'],
                'lon': row['lon'],
                'population': row['population']
            })

    return pd.DataFrame(connected_centers)
