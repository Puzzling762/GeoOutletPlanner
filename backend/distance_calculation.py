import pandas as pd
from optimization import vectorized_gravity_model

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate geodesic distance between two points in kilometers."""
    from geopy.distance import geodesic
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
    distances, interactions = vectorized_gravity_model(outlets, demand_centers)
    results = []

    for i, outlet_id in enumerate(outlets['id']):
        for j, demand_id in enumerate(demand_centers['id']):
            results.append({
                'outlet_id': outlet_id,
                'demand_id': demand_id,
                'distance': distances[i, j],
                'interaction': interactions[i, j]
            })

    return pd.DataFrame(results)
