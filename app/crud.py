# app/crud.py

from typing import Optional
from bson.objectid import ObjectId
from datetime import datetime

from app.db import master_db
from app.utils import slugify
from app.auth import hash_password, verify_password

ORG_COLL = master_db["organizations"]


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


async def create_organization(org_name: str, admin_email: str, admin_password: str) -> dict:
    """
    Create org metadata and a dynamic collection named org_<slug>.
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

    res = await ORG_COLL.insert_one({
        "organization_name": org_name,
        "collection_name": collection_name,
        "admin": admin_doc,
        "created_at": datetime.utcnow()
    })

    # create the dynamic collection (insert dummy then remove)
    col = master_db[collection_name]
    await col.insert_one({"_init": True})
    await col.delete_many({"_init": True})

    return {
        "organization_name": org_name,
        "collection_name": collection_name,
        "admin_email": admin_email,
        "id": str(res.inserted_id)
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
            "collection_name": doc["collection_name"]
        }
    return None


async def delete_organization(org_name: str) -> bool:
    """
    Delete org metadata and drop the dynamic collection if present.
    Returns True if deleted, False if not found.
    """
    doc = await ORG_COLL.find_one_and_delete({"organization_name": org_name})
    if not doc:
        return False
    colname = doc["collection_name"]
    if colname in await master_db.list_collection_names():
        await master_db.drop_collection(colname)
    return True


async def update_organization(org_name: str,
                              new_org_name: Optional[str] = None,
                              email: Optional[str] = None,
                              password: Optional[str] = None) -> bool:
    """
    Update org metadata. If new_org_name provided, create new collection org_<newslug>,
    copy documents (simple approach), drop old collection, and update master metadata.
    Note: for large datasets prefer renameCollection (requires admin privileges) or background migration.
    """
    doc = await ORG_COLL.find_one({"organization_name": org_name})
    if not doc:
        raise ValueError("Organization not found")

    updates = {}
    if new_org_name:
        new_slug = slugify(new_org_name)
        new_collection_name = f"org_{new_slug}"

        src_coll = master_db[doc["collection_name"]]
        dst_coll = master_db[new_collection_name]

        # copy documents (works for small datasets)
        async for item in src_coll.find({}):
            item.pop("_id", None)
            await dst_coll.insert_one(item)

        # drop old collection
        await master_db.drop_collection(doc["collection_name"])

        updates["organization_name"] = new_org_name
        updates["collection_name"] = new_collection_name

    if email or password:
        admin = doc["admin"]
        if email:
            admin["email"] = email
        if password:
            admin["password_hash"] = hash_password(password)
        updates["admin"] = admin

    if updates:
        await ORG_COLL.update_one({"_id": doc["_id"]}, {"$set": updates})

    return True
