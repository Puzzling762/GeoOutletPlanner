import os
import logging
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point, shape
from pymongo import MongoClient
from bson.objectid import ObjectId
from dotenv import load_dotenv
from optimization import optimize_outlet_location_fast as optimize_outlet_location
from visualization import visualize_map
from osm_utils import load_graph_from_osrm_route

# Load environment variables
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")

# Setup logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for cross-origin requests

# Connect to MongoDB
try:
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client["app_data"]  # Corrected database name
    districts_collection = db["districts_geojson"]  # Corrected collection name
    population_collection = db["district_population"]  # Corrected collection name
    maps_collection = db["maps"]  # Collection for storing generated maps
    logging.info("Connected to MongoDB successfully.")

    # Create a 2dsphere index on the 'geometry' field
    districts_collection.create_index([("geometry", "2dsphere")])
    logging.info("2dsphere index created on 'geometry' field in districts collection.")

except Exception as e:
    logging.error(f"Failed to connect to MongoDB: {e}")
    raise RuntimeError("Could not connect to MongoDB. Check your MONGO_URI in the .env file.")

# Load districts GeoJSON from MongoDB
try:
    districts_data = districts_collection.find_one()
    if not districts_data or "features" not in districts_data:
        raise RuntimeError("Districts GeoJSON not found or invalid in MongoDB. Please populate the 'districts_geojson' collection.")

    # Convert GeoJSON to GeoDataFrame
    districts_gdf = gpd.GeoDataFrame.from_features(districts_data["features"])
    districts_gdf['geometry'] = districts_gdf['geometry'].apply(shape)  # Ensure Shapely geometries
    logging.info("Districts GeoJSON loaded successfully.")
except Exception as e:
    logging.error(f"Error loading districts GeoJSON: {e}")
    raise RuntimeError("Failed to load districts GeoJSON from MongoDB.")

# Load population data from MongoDB
try:
    population_data = list(population_collection.find())
    if not population_data:
        logging.warning("No population data found in MongoDB. Using an empty dataset.")
        district_population_df = pd.DataFrame(columns=["district", "population"])
    else:
        district_population_df = pd.DataFrame(population_data)
        if not {"district", "population"}.issubset(district_population_df.columns):
            raise ValueError("Population data is missing required columns ('district', 'population').")
        district_population_df['district'] = district_population_df['district'].str.strip().str.lower()
    logging.info("Population data loaded successfully.")
except Exception as e:
    logging.error(f"Error loading population data: {e}")
    raise RuntimeError("Failed to load population data from MongoDB.")

# Utility functions
def normalize_name(name):
    return name.lower().strip() if name else None

def find_district(lat, lon):
    try:
        point = Point(lon, lat)
        for _, row in districts_gdf.iterrows():
            if row['geometry'].contains(point):
                district_name = row.get('NAME_2', None)
                if not district_name:
                    logging.warning(f"No district name found for geometry at ({lat}, {lon})")
                    return "Unknown"
                normalized_district = normalize_name(district_name)
                logging.debug(f"District found for ({lat}, {lon}): {normalized_district}")
                return normalized_district
        logging.warning(f"No district found for ({lat}, {lon})")
        return "Unknown"
    except Exception as e:
        logging.error(f"Error finding district: {e}")
        return "Error"

def get_population_by_district(district_name):
    try:
        normalized_name = normalize_name(district_name)
        logging.debug(f"Fetching population for district: {normalized_name}")
        population_row = district_population_df[district_population_df["district"] == normalized_name]
        if not population_row.empty:
            return int(population_row.iloc[0]["population"])
        logging.warning(f"No population data found for {normalized_name}. Using default.")
        return 2876546  # Default population
    except Exception as e:
        logging.error(f"Error fetching population for '{district_name}': {e}")
        return 2876546  # Default value on error

# Routes
@app.route('/demand-centers', methods=['POST'])
def demand_centers():
    data = request.json
    logging.info(f"Received data: {data}")

    if not data or 'demandCenters' not in data:
        return jsonify({'error': 'Invalid data: Missing "demandCenters" field'}), 400

    try:
        demand_centers = pd.DataFrame(data['demandCenters'])
        if 'latitude' not in demand_centers.columns or 'longitude' not in demand_centers.columns:
            raise ValueError("Invalid demand center data: Missing 'latitude' or 'longitude' fields.")
        demand_centers.rename(columns={'latitude': 'lat', 'longitude': 'lon'}, inplace=True)

        # Assign districts and population
        demand_centers['district'] = demand_centers.apply(lambda row: find_district(row['lat'], row['lon']), axis=1)
        demand_centers['population'] = demand_centers.apply(
            lambda row: get_population_by_district(row['district']) if pd.isna(row.get('population', None)) else row['population'], axis=1
        )
        demand_centers['population'] = demand_centers['population'].fillna(2876546)
        demand_centers.loc[demand_centers['population'] <= 0, 'population'] = 2876546

        logging.debug(f"Final demand centers: {demand_centers}")

        # Determine bounding box for road graph
        min_lat, max_lat = demand_centers['lat'].min(), demand_centers['lat'].max()
        min_lon, max_lon = demand_centers['lon'].min(), demand_centers['lon'].max()

        logging.info(f"Bounding box: ({min_lat}, {min_lon}) to ({max_lat}, {max_lon})")

        # Load road network
        road_graph = load_graph_from_osrm_route(min_lat, min_lon, max_lat, max_lon)
        if road_graph is None:
            logging.warning("Road graph failed to load. Using GIS fallback.")
            return jsonify({
                'message': 'GIS fallback used.',
                'demand_centers': demand_centers.to_dict(orient='records')
            })

        # Select initial outlets
        n_outlets = min(5, len(demand_centers))
        initial_outlets = demand_centers.sample(n_outlets, random_state=42).reset_index(drop=True)
        initial_outlets['id'] = range(1, n_outlets + 1)

        logging.debug(f"Initialized outlets: {initial_outlets}")

        # Optimize outlets
        logging.info("Optimizing outlet locations...")
        assignments, optimized_outlets = optimize_outlet_location(initial_outlets, demand_centers, road_graph)
        logging.info("Optimization completed.")

        # Generate GeoJSON map
        geojson_data = visualize_map(optimized_outlets, demand_centers, assignments, road_graph)

        # Save map to MongoDB
        map_id = maps_collection.insert_one({"data": geojson_data, "timestamp": time.time()}).inserted_id

        return jsonify({
            'message': 'Optimization successful!',
            'assignments': assignments.to_dict(orient='records'),
            'map_url': f'/download/{map_id}'
        })

    except Exception as e:
        logging.error(f"Error processing demand centers: {e}")
        return jsonify({'error': 'Failed to process data'}), 500

@app.route('/download/<map_id>', methods=['GET'])
def download_file(map_id):
    try:
        map_data = maps_collection.find_one({"_id": ObjectId(map_id)})
        if not map_data:
            return jsonify({'error': 'File not found'}), 404

        geojson_data = map_data['data']
        return jsonify(geojson_data)

    except Exception as e:
        logging.error(f"Error downloading file: {e}")
        return jsonify({'error': 'File not found'}), 404

if __name__ == '__main__':
    app.run(debug=True)
