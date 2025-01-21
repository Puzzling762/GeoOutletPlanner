import os
from dotenv import load_dotenv
from pymongo import MongoClient
import json

# Load environment variables from .env
load_dotenv()

# Get MongoDB URI from .env
MONGODB_URI = os.getenv("MONGO_URI")

if not MONGODB_URI:
    print("❌ MONGODB_URI is not set in .env!")
    exit(1)  # Exit if MongoDB URI is missing

print(f"✅ MONGODB_URI loaded successfully: {MONGODB_URI[:20]}...")  # Masked for security

# Connect to MongoDB
try:
    client = MongoClient(MONGODB_URI)
    client.admin.command("ping")  # Check connection
    print("✅ MongoDB connection successful!")
except Exception as e:
    print(f"❌ Error connecting to MongoDB: {e}")



db = client["district_data"]
districts_collection = db["district_geojson"]

# Fetch all documents in the collection
districts = list(districts_collection.find())

for district in districts:
    # Check if geometry is a string
    if isinstance(district.get("geometry"), str):
        # Convert geometry string to a JSON object
        district["geometry"] = json.loads(district["geometry"].replace("'", '"'))  # Replace single quotes with double quotes

        # Update the document in MongoDB
        districts_collection.update_one({"_id": district["_id"]}, {"$set": {"geometry": district["geometry"]}})

print("All geometry fields have been fixed.")
