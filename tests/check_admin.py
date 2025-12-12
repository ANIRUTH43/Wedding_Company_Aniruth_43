# check_admin.py
import asyncio
from dotenv import load_dotenv
import os
from passlib.context import CryptContext
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise SystemExit("MONGO_URI missing in .env")

client = AsyncIOMotorClient(MONGO_URI)
db = client["master_db"]
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def main():
    org_name = "Tesla"   # <- change to your org name
    doc = await db["organizations"].find_one({"organization_name": org_name})
    if not doc:
        print("Organization not found in DB:", org_name)
        return
    print("Found org:", doc["organization_name"])
    admin = doc.get("admin", {})
    print("Stored admin.email:", admin.get("email"))
    print("Stored password_hash:", admin.get("password_hash")[:20] + "..." if admin.get("password_hash") else None)

    # verify provided password:
    candidate = "123456"   # <- change to the password you used when creating org
    ok = pwd_ctx.verify(candidate, admin.get("password_hash"))
    print("Does candidate password match stored hash?", ok)

asyncio.run(main())
