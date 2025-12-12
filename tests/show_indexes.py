# show_indexes.py
import asyncio, os
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
load_dotenv()
client = AsyncIOMotorClient(os.getenv("MONGO_URI"))
db = client["master_db"]
async def main():
    print(await db["organizations"].index_information())
asyncio.run(main())
