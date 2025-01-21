from geopy.distance import geodesic
import pandas as pd

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate geodesic distance between two points in kilometers."""
    return geodesic((lat1, lon1), (lat2, lon2)).km


def gravity_model(population_i, population_j, distance_ij):
    """
    Gravity model formula to calculate interaction between two points.
    Avoids division by zero for zero distances.
    """
    if distance_ij == 0:
        return 0  # Avoid division by zero
    return (population_i * population_j) / (distance_ij ** 2)


def calculate_interactions(outlets, demand_centers):
    """
    Calculate interactions between outlets and demand centers using the gravity model.
    Returns a DataFrame of interactions.
    """
    interactions = []

    for _, outlet in outlets.iterrows():
        for _, demand in demand_centers.iterrows():
            distance = calculate_distance(outlet['lat'], outlet['lon'], demand['lat'], demand['lon'])
            interaction = gravity_model(outlet.get('population', 1), demand.get('population', 1), distance)

            interactions.append({
                'outlet_id': outlet['id'],
                'demand_id': demand['id'],
                'interaction': interaction,
                'distance': distance
            })

    return pd.DataFrame(interactions)
