import asyncio
from app.db import client

async def test():
    dbs = await client.list_database_names()
    print("Connected! Databases:", dbs)

asyncio.run(test())
