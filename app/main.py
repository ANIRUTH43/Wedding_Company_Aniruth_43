# app/main.py

from fastapi import FastAPI
from dotenv import load_dotenv
from app.routes import router
from app import crud

load_dotenv()

app = FastAPI(title="Org Management Service")

@app.on_event("startup")
async def startup_event():
    await crud.ensure_indexes()

# include all API routes
app.include_router(router)
