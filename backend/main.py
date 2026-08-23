import sys
import os

# Ensure backend directory is in python search path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)


import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database.database import init_db
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
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

from database.github_sync import download_db, upload_db_async
from fastapi import Request

# Register API Router
app.include_router(router, prefix="/api")

# HTTP Middleware to sync database mutations back to GitHub asynchronously
@app.middleware("http")
async def db_sync_middleware(request: Request, call_next):
    response = await call_next(request)
    if request.method in ["POST", "PUT", "DELETE"] and 200 <= response.status_code < 300:
        upload_db_async()
    return response

@app.on_event("startup")
def startup_event():
    # Download the latest database from GitHub before initializing
    download_db()
    # Automatically initialize SQLite schemas and seeds
    init_db()

@app.get("/")
def read_root():
    return {"status": "online", "message": "Traffic Rule Compliance Engine API is running"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
