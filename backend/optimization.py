import pandas as pd
import numpy as np
import logging  # Fix for undefined logging
from osm_utils import calculate_road_distance, find_nearest_node

def precompute_distances(outlets, demand_centers, road_graph):
    """
    Precompute distances between all outlets and demand centers using OSRM.
    Optimized with caching and vectorized calculations.
    """
    distances = []
    for _, outlet in outlets.iterrows():
        for _, demand in demand_centers.iterrows():
            distance = calculate_road_distance(
                road_graph, outlet['lat'], outlet['lon'], demand['lat'], demand['lon']
            )
            distances.append((outlet['id'], demand['id'], distance))
    return pd.DataFrame(distances, columns=['outlet_id', 'demand_id', 'distance'])


def vectorized_gravity_model(outlets, demand_centers):
    """
    Vectorized calculation of distances and interactions using NumPy and pandas.
    """
    # Convert coordinates to radians
    outlet_coords = np.radians(outlets[['lat', 'lon']].to_numpy())
    demand_coords = np.radians(demand_centers[['lat', 'lon']].to_numpy())

    # Expand for broadcasting
    lat1, lon1 = outlet_coords[:, 0:1], outlet_coords[:, 1:2]
    lat2, lon2 = demand_coords[:, 0:1], demand_coords[:, 1:2].T
    dlat, dlon = lat2 - lat1, lon2 - lon1

    # Haversine formula for distances
    a = np.sin(dlat / 2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    distances = 6371 * c  # Earth radius in km

    # Gravity model interactions
    outlet_pop = outlets['population'].to_numpy()[:, None]  # Shape (n_outlets, 1)
    demand_pop = demand_centers['population'].to_numpy()[None, :]  # Shape (1, n_demand_centers)
    interactions = (outlet_pop * demand_pop) / (distances ** 2)
    interactions[np.isnan(interactions)] = 0  # Avoid NaNs

    return distances, interactions


def assign_demand_to_outlets_fast(distances, demand_centers):
    """
    Assign demand centers to the nearest outlet based on precomputed distances.
    Ensures all demand centers are assigned.
    """
    min_distances = distances.loc[distances.groupby('demand_id')['distance'].idxmin()]
    unassigned = demand_centers[~demand_centers['id'].isin(min_distances['demand_id'])]

    if not unassigned.empty:
        logging.warning(f"Unassigned demand centers: {len(unassigned)}")
        for _, row in unassigned.iterrows():
            logging.warning(f"Demand center {row['id']} could not be assigned to an outlet.")

    return min_distances


def optimize_outlet_location_fast(outlets, demand_centers, road_graph):
    """
    Optimized version of outlet location optimization using vectorized calculations.
    """
    # Precompute distances
    distances = precompute_distances(outlets, demand_centers, road_graph)

    # Assign demand to outlets
    assignments = assign_demand_to_outlets_fast(distances, demand_centers)

    # Optimization loop with logging and stagnation detection
    max_iterations = 10  # Limit the number of iterations
    for iteration in range(max_iterations):
        logging.info(f"Iteration {iteration + 1}: {len(outlets)} outlets remaining.")

        outlet_dropped = False  # Track if any outlet was dropped
        for i, outlet in outlets.iterrows():
            # Test removing one outlet
            test_outlets = outlets.drop(i)
            test_distances = precompute_distances(test_outlets, demand_centers, road_graph)
            test_assignments = assign_demand_to_outlets_fast(test_distances, demand_centers)

            # If successful, update outlets and assignments
            if len(test_assignments) == len(demand_centers):
                outlets = test_outlets
                assignments = test_assignments
                outlet_dropped = True
                logging.info(f"Outlet {outlet['id']} removed.")
                break

        if not outlet_dropped:  # No outlets could be removed, stop early
            logging.warning("No outlets could be removed. Stopping optimization.")
            break

    # Update outlet locations
    optimized_outlets = update_outlet_locations(assignments, demand_centers, outlets)
    return assignments, optimized_outlets


def update_outlet_locations(assignments, demand_centers, outlets):
    """
    Update outlet locations to the weighted mean of their assigned demand centers.
    """
    optimized_outlets = []

    for outlet_id, group in assignments.groupby('outlet_id'):
        assigned_demand = demand_centers[demand_centers['id'].isin(group['demand_id'])]

        if len(assigned_demand) > 0:
            lat = (assigned_demand['lat'] * assigned_demand['population']).sum() / assigned_demand['population'].sum()
            lon = (assigned_demand['lon'] * assigned_demand['population']).sum() / assigned_demand['population'].sum()
        else:
            lat, lon = outlets.loc[outlets['id'] == outlet_id, ['lat', 'lon']].values[0]

        optimized_outlets.append({'id': outlet_id, 'lat': lat, 'lon': lon, 'population': 1})

    return pd.DataFrame(optimized_outlets)
