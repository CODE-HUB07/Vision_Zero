import sys
import os

# Ensure backend directory is in python search path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database.database import init_db
from api.api_router import router

app = FastAPI(
    title="Traffic Rule Compliance Engine API",
    description="Offline-first safety, compliance, scoring and gamification API",
    version="1.0.0"
)

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Router
app.include_router(router, prefix="/api")

@app.on_event("startup")
def startup_event():
    # Automatically initialize SQLite schemas and seeds
    init_db()

@app.get("/")
def read_root():
    return {"status": "online", "message": "Traffic Rule Compliance Engine API is running"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
