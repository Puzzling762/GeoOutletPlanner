import os
import logging
import time
import threading
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from optimization import optimize_outlet_location_fast as optimize_outlet_location
from visualization import visualize_map
from osm_utils import load_graph_from_osrm_route
import streamlit as st
import requests
import json

# Setup logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

# Flask app setup
app = Flask(__name__)
CORS(app)  # Enable CORS for cross-origin requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MAPS_FOLDER = os.path.join(BASE_DIR, "maps")
os.makedirs(MAPS_FOLDER, exist_ok=True)

DISTRICTS_FILE = os.path.join(BASE_DIR, "india_district.geojson")
districts_gdf = gpd.read_file(DISTRICTS_FILE)

POPULATION_DATA_FILE = os.path.join(BASE_DIR, "district_population_all_pages.csv")

if os.path.exists(POPULATION_DATA_FILE):
    district_population_df = pd.read_csv(POPULATION_DATA_FILE)
    district_population_df.columns = district_population_df.columns.str.strip().str.lower()
    district_population_df['district'] = district_population_df['district'].str.strip().str.lower()
    logging.debug(f"Loaded district population data with columns: {district_population_df.columns.tolist()}")
else:
    district_population_df = pd.DataFrame(columns=["district", "population"])
    logging.warning(f"Population data file '{POPULATION_DATA_FILE}' not found. Using default values.")

def normalize_name(name):
    return name.lower().strip() if name else None

def find_district(lat, lon):
    try:
        point = Point(lon, lat)
        for _, row in districts_gdf.iterrows():
            if row['geometry'].contains(point):
                normalized_district = normalize_name(row['NAME_2'])
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

@app.route('/demand-centers', methods=['POST'])
def demand_centers():
    data = request.json
    logging.info(f"Received data: {data}")

    if not data or not ('demandCenters' in data or 'locations' in data):
        return jsonify({'error': 'Invalid data'}), 400

    try:
        if 'demandCenters' in data:
            demand_centers = pd.DataFrame(data['demandCenters']).rename(columns={'latitude': 'lat', 'longitude': 'lon'})
            logging.debug(f"Processed demand centers: {demand_centers}")

            demand_centers['district'] = demand_centers.apply(lambda row: find_district(row['lat'], row['lon']), axis=1)
            demand_centers['population'] = demand_centers.apply(
                lambda row: get_population_by_district(row['district']) if pd.isna(row.get('population', None)) else row['population'], axis=1
            )
            demand_centers['population'] = demand_centers['population'].fillna(2876546)
            demand_centers.loc[demand_centers['population'] <= 0, 'population'] = 2876546

            logging.debug(f"Final demand centers: {demand_centers}")

            min_lat, max_lat = demand_centers['lat'].min(), demand_centers['lat'].max()
            min_lon, max_lon = demand_centers['lon'].min(), demand_centers['lon'].max()

            logging.info(f"Bounding box: ({min_lat}, {min_lon}) to ({max_lat}, {max_lon})")

            road_graph = load_graph_from_osrm_route(min_lat, min_lon, max_lat, max_lon)
            if road_graph is None:
                logging.warning("Road graph failed to load. Using GIS fallback.")
                return jsonify({
                    'message': 'GIS fallback used.',
                    'demand_centers': demand_centers.to_dict(orient='records')
                })

            n_outlets = min(5, len(demand_centers))
            initial_outlets = demand_centers.sample(n_outlets, random_state=42).reset_index(drop=True)
            initial_outlets['id'] = range(1, n_outlets + 1)

            logging.debug(f"Initialized outlets: {initial_outlets}")

            logging.info("Optimizing outlet locations...")
            assignments, optimized_outlets = optimize_outlet_location(initial_outlets, demand_centers, road_graph)
            logging.info("Optimization completed.")

            map_file_path = os.path.join(MAPS_FOLDER, "optimized_retail_map_with_connections.geojson")
            visualize_map(optimized_outlets, demand_centers, assignments, road_graph, map_file_path=map_file_path)

            while not os.path.exists(map_file_path):
                time.sleep(0.1)
            time.sleep(0.5)

            return jsonify({
                'message': 'Optimization successful!',
                'assignments': assignments.to_dict(orient='records'),
                'map_url': f'/download/{os.path.basename(map_file_path)}?t={int(time.time())}'
            })

    except Exception as e:
        logging.error(f"Error processing demand centers: {e}")
        return jsonify({'error': 'Failed to process data'}), 500

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    try:
        response = send_from_directory(MAPS_FOLDER, filename, as_attachment=False)
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Expires"] = "0"
        response.headers["Pragma"] = "no-cache"
        return response
    except Exception as e:
        logging.error(f"Error downloading file: {e}")
        return jsonify({'error': 'File not found'}), 404

# Streamlit setup
def run_streamlit():
    st.title("Optimal Outlet Locator")
    st.write("Enter demand center data to generate optimal retail outlet locations.")

    num_centers = st.number_input("Number of Demand Centers", min_value=1, step=1, value=1)

    st.write("Enter Latitude and Longitude for each Demand Center:")
    demand_centers = []

    for i in range(num_centers):
        col1, col2 = st.columns(2)
        with col1:
            lat = st.number_input(f"Latitude {i + 1}", key=f"lat_{i}")
        with col2:
            lon = st.number_input(f"Longitude {i + 1}", key=f"lon_{i}")
        
        demand_centers.append({"id": i + 1, "latitude": lat, "longitude": lon})

    if st.button("Generate Outlets"):
        progress_bar=st.progress(0)
        try:
            progress_bar.progress(10)
            response = requests.post(f"http://localhost:5000/demand-centers", json={"demandCenters": demand_centers})
            progress_bar.progress(50)
            response_data = response.json()

            if response.status_code == 200:
                progress_bar.progress(80)
                st.success("Optimization successful!")
                map_url = response_data.get("map_url")
                assignments = pd.DataFrame(response_data.get("assignments", []))

                st.write("Assignments:")
                st.dataframe(assignments)

                if map_url:
                    geojson_url = f"http://localhost:5000{map_url}"
                    st.markdown(f"[Download GeoJSON File]({geojson_url})", unsafe_allow_html=True)

                    def view_geojson():
                        try:
                            geojson_data = requests.get(geojson_url).json()
                            geojson_string = json.dumps(geojson_data)
                            geojson_encoded = requests.utils.quote(geojson_string)
                            geojson_io_url = f"https://geojson.io/#data=data:application/json,{geojson_encoded}"
                            st.markdown(f'<a href="{geojson_io_url}" target="_blank">View in Mapbox/GeoJSON Viewer</a>', unsafe_allow_html=True)
                        except Exception as e:
                            st.error(f"Failed to load GeoJSON: {e}")

                    view_geojson()
                progress_bar.progress(100)

            else:
                st.error(f"Error: {response_data.get('error', 'Unknown error')}")

        except Exception as e:
            st.error(f"Failed to connect to the backend: {e}")

# Run Flask in a separate thread
def run_flask():
    app.run(debug=True, use_reloader=False)

if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    run_streamlit()
