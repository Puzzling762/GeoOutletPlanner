import streamlit as st
import requests
import pandas as pd
import json

FLASK_API_URL = "http://localhost:5000"  # URL of your Flask app

st.title("Optimal Outlet Locator")
st.write("Enter demand center data to generate optimal retail outlet locations.")

# Step 1: Input Number of Demand Centers
num_centers = st.number_input("Number of Demand Centers", min_value=1, step=1, value=1)

# Step 2: Input Demand Centers (Latitude and Longitude)
st.write("Enter Latitude and Longitude for each Demand Center:")
demand_centers = []

for i in range(num_centers):
    col1, col2 = st.columns(2)
    with col1:
        lat = st.number_input(f"Latitude {i + 1}", key=f"lat_{i}")
    with col2:
        lon = st.number_input(f"Longitude {i + 1}", key=f"lon_{i}")
    
    # Add 'id' field to each demand center for the backend to process
    demand_centers.append({"id": i + 1, "latitude": lat, "longitude": lon})

# Step 3: Submit Data to Backend
if st.button("Generate Outlets"):
    try:
        # Send data to Flask backend
        response = requests.post(f"{FLASK_API_URL}/demand-centers", json={"demandCenters": demand_centers})
        response_data = response.json()

        if response.status_code == 200:
            st.success("Optimization successful!")
            map_url = response_data.get("map_url")
            assignments = pd.DataFrame(response_data.get("assignments", []))

            st.write("Assignments:")
            st.dataframe(assignments)

            # GeoJSON File Link
            if map_url:
                geojson_url = f"{FLASK_API_URL}{map_url}"
                st.markdown(f"[Download GeoJSON File]({geojson_url})", unsafe_allow_html=True)
                
                # Function to open the GeoJSON in geojson.io
                def view_geojson():
                    try:
                        geojson_data = requests.get(geojson_url).json()  # Fetch GeoJSON data
                        geojson_string = json.dumps(geojson_data)  # Convert to JSON string
                        geojson_encoded = requests.utils.quote(geojson_string)  # URL-encode the data
                        geojson_io_url = f"https://geojson.io/#data=data:application/json,{geojson_encoded}"
                        # Open in new tab (GeoJSON.io)
                        st.markdown(f'<a href="{geojson_io_url}" target="_blank">View in Mapbox/GeoJSON Viewer</a>', unsafe_allow_html=True)
                    except Exception as e:
                        st.error(f"Failed to load GeoJSON: {e}")

                view_geojson()  # Invoke the function to show GeoJSON link

        else:
            st.error(f"Error: {response_data.get('error', 'Unknown error')}")

    except Exception as e:
        st.error(f"Failed to connect to the backend: {e}")
