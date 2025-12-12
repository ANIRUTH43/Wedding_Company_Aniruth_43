# app/crud.py
from typing import Optional
from bson.objectid import ObjectId
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from app.db import master_db, client as default_client
from app.utils import slugify
from app.auth import hash_password, verify_password

ORG_COLL = master_db["organizations"]

# Cache for tenant-specific database connections
_tenant_clients = {}

async def ensure_indexes() -> None:
    """
    Create useful indexes (run at startup).
    - unique organization_name
    - unique admin.email
    """
    await ORG_COLL.create_index("organization_name", unique=True)
    await ORG_COLL.create_index("admin.email", unique=True)

async def organization_exists(name: str) -> bool:
    return await ORG_COLL.find_one({"organization_name": name}) is not None

def get_tenant_db(org_doc: dict):
    """
    Get the appropriate database connection for a tenant.
    Returns either a dedicated DB connection or the shared master_db.
    """
    db_type = org_doc.get("db_type", "shared")
    
    if db_type == "dedicated":
        db_uri = org_doc.get("connection_details", {}).get("db_uri")
        db_name = org_doc.get("connection_details", {}).get("db_name")
        
        if db_uri and db_name:
            # Use cached connection or create new one
            cache_key = f"{db_uri}_{db_name}"
            if cache_key not in _tenant_clients:
                _tenant_clients[cache_key] = AsyncIOMotorClient(db_uri)
            
            return _tenant_clients[cache_key][db_name]
    
    # Default: use shared master_db
    return default_client[org_doc.get("db_name", "master_db")]

async def create_organization(
    org_name: str, 
    admin_email: str, 
    admin_password: str,
    db_uri: Optional[str] = None,
    db_name: Optional[str] = None
) -> dict:
    """
    Create org metadata and a dynamic collection/database.
    
    Two modes:
    1. Shared mode (default): Creates collection in master_db
    2. Dedicated mode: Uses separate database connection if db_uri provided
    """
    if await organization_exists(org_name):
        raise ValueError("Organization already exists")

    slug = slugify(org_name)
    collection_name = f"org_{slug}"
    
    admin_doc = {
        "email": admin_email,
        "password_hash": hash_password(admin_password),
        "role": "admin",
        "created_at": datetime.utcnow(),
    }
    
    org_metadata = {
        "organization_name": org_name,
        "collection_name": collection_name,
        "admin": admin_doc,
        "created_at": datetime.utcnow()
    }
    
    # Determine database type and connection details
    if db_uri and db_name:
        # Dedicated database mode
        org_metadata["db_type"] = "dedicated"
        org_metadata["connection_details"] = {
            "db_uri": db_uri,  # In production, encrypt this!
            "db_name": db_name
        }
        org_metadata["db_name"] = db_name
        
        # Create collection in dedicated database
        try:
            tenant_client = AsyncIOMotorClient(db_uri)
            tenant_db = tenant_client[db_name]
            col = tenant_db[collection_name]
            await col.insert_one({"_init": True})
            await col.delete_many({"_init": True})
        except Exception as e:
            raise ValueError(f"Failed to connect to dedicated database: {str(e)}")
    else:
        # Shared database mode (default)
        org_metadata["db_type"] = "shared"
        org_metadata["db_name"] = "master_db"
        
        # Create the dynamic collection in master_db
        col = master_db[collection_name]
        await col.insert_one({"_init": True})
        await col.delete_many({"_init": True})
    
    res = await ORG_COLL.insert_one(org_metadata)
    
    return {
        "organization_name": org_name,
        "collection_name": collection_name,
        "admin_email": admin_email,
        "id": str(res.inserted_id),
        "db_type": org_metadata["db_type"],
        "db_name": org_metadata.get("db_name")
    }

async def get_organization(org_name: str) -> Optional[dict]:
    doc = await ORG_COLL.find_one({"organization_name": org_name})
    if not doc:
        return None
    # convert _id to str to be JSON serializable if needed
    doc["_id"] = str(doc["_id"])
    return doc

async def admin_authenticate(email: str, password: str) -> Optional[dict]:
    """
    Authenticate admin by email/password. Returns minimal org/admin info on success.
    """
    doc = await ORG_COLL.find_one({"admin.email": email})
    if not doc:
        return None
    
    admin = doc["admin"]
    if verify_password(password, admin["password_hash"]):
        return {
            "org_id": str(doc["_id"]),
            "org_name": doc["organization_name"],
            "admin_email": admin["email"],
            "collection_name": doc["collection_name"],
            "db_type": doc.get("db_type", "shared"),
            "db_name": doc.get("db_name", "master_db")
        }
    
    return None

async def delete_organization(org_name: str) -> bool:
    """
    Delete org metadata and drop the dynamic collection/database if present.
    Returns True if deleted, False if not found.
    """
    doc = await ORG_COLL.find_one_and_delete({"organization_name": org_name})
    if not doc:
        return False
    
    colname = doc["collection_name"]
    db_type = doc.get("db_type", "shared")
    
    if db_type == "shared":
        # Drop collection from master_db
        if colname in await master_db.list_collection_names():
            await master_db.drop_collection(colname)
    else:
        # Drop collection from dedicated database
        tenant_db = get_tenant_db(doc)
        if tenant_db and colname in await tenant_db.list_collection_names():
            await tenant_db.drop_collection(colname)
    
    return True

async def update_organization(
    org_name: str,
    new_org_name: Optional[str] = None,
    email: Optional[str] = None,
    password: Optional[str] = None,
    db_uri: Optional[str] = None,
    db_name: Optional[str] = None
) -> bool:
    """
    Update org metadata. If new_org_name provided, create new collection org_,
    copy documents (simple approach), drop old collection, and update master metadata.
    Note: for large datasets prefer renameCollection (requires admin privileges) or background migration.
    """
    doc = await ORG_COLL.find_one({"organization_name": org_name})
    if not doc:
        raise ValueError("Organization not found")
    
    updates = {}
    
    # Get current tenant database
    current_db = get_tenant_db(doc)
    
    if new_org_name:
        new_slug = slugify(new_org_name)
        new_collection_name = f"org_{new_slug}"
        
        src_coll = current_db[doc["collection_name"]]
        dst_coll = current_db[new_collection_name]
        
        # copy documents (works for small datasets)
        async for item in src_coll.find({}):
            item.pop("_id", None)
            await dst_coll.insert_one(item)
        
        # drop old collection
        await current_db.drop_collection(doc["collection_name"])
        
        updates["organization_name"] = new_org_name
        updates["collection_name"] = new_collection_name
    
    if email or password:
        admin = doc["admin"]
        if email:
            admin["email"] = email
        if password:
            admin["password_hash"] = hash_password(password)
        updates["admin"] = admin
    
    # Update connection details if provided
    if db_uri or db_name:
        connection_details = doc.get("connection_details", {})
        if db_uri:
            connection_details["db_uri"] = db_uri
            updates["db_type"] = "dedicated"
        if db_name:
            connection_details["db_name"] = db_name
            updates["db_name"] = db_name
        if connection_details:
            updates["connection_details"] = connection_details
    
    if updates:
        await ORG_COLL.update_one({"_id": doc["_id"]}, {"$set": updates})
    
    return True
