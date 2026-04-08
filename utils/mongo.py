import os
from pymongo import MongoClient

mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017/")

client = MongoClient(mongo_uri)
db = client["PlantConnectome"]

try:
    server_info = client.server_info()
    print("Connected to MongoDB Version:", server_info["version"])
except Exception as e:
    print(f"Warning: Could not verify MongoDB connection: {e}")
    print("The app will attempt to connect when the first request is made.")
