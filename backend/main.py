from input_handler import process_inputs
from optimization import optimize_outlet_location
from visualization import visualize_map
from sklearn.cluster import KMeans
import pandas as pd

# Input: Provided demand center data with population
demand_centers = [
    # Agra District
    {'id': 1, 'latitude': 27.1767, 'longitude': 78.0081, 'population': 5000},  # Agra
    {'id': 2, 'latitude': 27.1592, 'longitude': 78.3965, 'population': 3000},  # Firozabad
    {'id': 3, 'latitude': 27.2228, 'longitude': 78.2473, 'population': 4000},  # Tundla

    # Meerut District
    {'id': 4, 'latitude': 28.9845, 'longitude': 77.7050, 'population': 8000},  # Meerut
    {'id': 5, 'latitude': 28.7452, 'longitude': 77.7813, 'population': 6000},  # Hapur
    {'id': 6, 'latitude': 29.0506, 'longitude': 77.8343, 'population': 3500},  # Mawana

    # Mathura District
    {'id': 7, 'latitude': 27.4979, 'longitude': 77.6711, 'population': 7000},  # Mathura
    {'id': 8, 'latitude': 27.5706, 'longitude': 77.6961, 'population': 4000},  # Vrindavan
    {'id': 9, 'latitude': 27.3190, 'longitude': 77.7030, 'population': 3000},  # Raya

    # Muzaffarnagar District
    {'id': 10, 'latitude': 29.4677, 'longitude': 77.6731, 'population': 9000},  # Muzaffarnagar
    {'id': 11, 'latitude': 29.4210, 'longitude': 77.5301, 'population': 5000},  # Shahpur
    {'id': 12, 'latitude': 29.3363, 'longitude': 77.6972, 'population': 4500},  # Khatauli

    # Hardoi District
    {'id': 13, 'latitude': 27.3944, 'longitude': 79.9841, 'population': 6000},  # Hardoi
    {'id': 14, 'latitude': 27.1742, 'longitude': 79.9574, 'population': 3000},  # Sandila
    {'id': 15, 'latitude': 27.1393, 'longitude': 79.9321, 'population': 4000},  # Bilgram
]

# Process input data
demand_centers_df = pd.DataFrame(demand_centers)
demand_centers_df = demand_centers_df.rename(columns={"latitude": "lat", "longitude": "lon"})

# Perform KMeans clustering to identify initial outlet locations
n_outlets = min(5, len(demand_centers_df))  # Ensure n_outlets <= number of demand centers
kmeans = KMeans(n_clusters=n_outlets, random_state=42)
kmeans.fit(demand_centers_df[['lat', 'lon']])

# Create a DataFrame for the outlets
outlets_df = pd.DataFrame({
    'id': range(1, n_outlets + 1),
    'lat': kmeans.cluster_centers_[:, 0],
    'lon': kmeans.cluster_centers_[:, 1],
    'population': [1] * n_outlets  # Default population for now, you can adjust this based on demand centers' clusters
})

# Perform optimization
optimal_outlets = optimize_outlet_location(outlets_df, demand_centers_df)

# Create assignments DataFrame
assignments = optimal_outlets[['demand_id', 'outlet_id']]

# Group demand centers by outlet and display in the desired format
outlet_assignments = {outlet_id: [] for outlet_id in outlets_df['id']}

# Populate the outlet assignments dictionary
for index, row in assignments.iterrows():
    outlet_assignments[row['outlet_id']].append(row['demand_id'])

# Print the outlet assignments in the desired format, including population
for outlet_id, demand_ids in outlet_assignments.items():
    print(f"Retail Outlet {outlet_id}.0 is connected to the following Demand Centers:")
    for demand_id in demand_ids:
        demand_center = demand_centers_df[demand_centers_df['id'] == demand_id].iloc[0]
        print(f"  DC {demand_id} at ({demand_center['lat']}, {demand_center['lon']}) with population {demand_center['population']}")
    print()  # Add a newline for better readability

# Visualize the results with connections
visualize_map(outlets_df, demand_centers_df, assignments)
