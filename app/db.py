# app/db.py
"""
Database configuration and connection management.
Handles MongoDB connections with SSL/TLS support for Python 3.13+
"""

import os
import ssl
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB Configuration
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise ValueError("MONGO_URI environment variable is not set")

# Database names
MASTER_DB_NAME = "master_db"
ORG_COLLECTION_NAME = "organizations"

# Create SSL context for Python 3.13 compatibility
def create_mongo_client():
    """Create MongoDB client with proper SSL/TLS configuration for Python 3.13"""
    
    # SSL context configuration
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    # Client configuration with SSL and timeout settings
    client_kwargs = {
        "tls": True,
        "tlsAllowInvalidCertificates": True,
        "serverSelectionTimeoutMS": 5000,  # 5 seconds (reduced for faster failures)
        "connectTimeoutMS": 5000,
        "socketTimeoutMS": 5000,
        "maxPoolSize": 10,
        "minPoolSize": 1,
        "retryWrites": True,
        "w": "majority"
    }
    
    try:
        client = AsyncIOMotorClient(MONGO_URI, **client_kwargs)
        return client
    except Exception as e:
        print(f"Error creating MongoDB client: {e}")
        raise


# Create global client instance
try:
    client = create_mongo_client()
    master_db = client[MASTER_DB_NAME]
    organizations_collection = master_db[ORG_COLLECTION_NAME]
    print(f"MongoDB client initialized successfully")
except Exception as e:
    print(f"Failed to initialize MongoDB client: {e}")
    # Create a dummy client that will fail gracefully
    client = None
    master_db = None
    organizations_collection = None


# Helper function to get database by name
def get_database(db_name: str):
    """Get database instance by name"""
    if client is None:
        raise ConnectionError("MongoDB client not initialized")
    return client[db_name]


# Helper function to test connection
async def test_connection():
    """Test MongoDB connection"""
    try:
        if client is None:
            return False
        await client.admin.command('ping')
        return True
    except Exception as e:
        print(f"MongoDB connection test failed: {e}")
        return False


# Export commonly used objects
__all__ = [
    'client',
    'master_db',
    'organizations_collection',
    'get_database',
    'test_connection',
    'MASTER_DB_NAME',
    'ORG_COLLECTION_NAME'
]
