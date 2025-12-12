import os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Load .env variables
load_dotenv()

# Get the Atlas connection string from .env
MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise ValueError("❌ MONGO_URI is missing in your .env file")

# Create the MongoDB client
client = AsyncIOMotorClient(MONGO_URI)

# Master database where organizations and metadata will be stored
master_db = client["master_db"]

# Export client + master_db for use in other files
__all__ = ["client", "master_db"]
