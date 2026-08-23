import os
import json
import base64
import urllib.request
import urllib.error
import threading

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO_OWNER = os.environ.get("GITHUB_REPO_OWNER", "CODE-HUB07")
REPO_NAME = os.environ.get("GITHUB_REPO_NAME", "Vision_Zero")
DB_FILE_PATH = "backend/database/traffic_compliance.db"

# Import DB_PATH from database configuration
from database.database import DB_PATH

upload_lock = threading.Lock()

def get_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "FastAPI-Vercel-Sync"
    }

def download_db():
    if not GITHUB_TOKEN:
        print("[GitHub Sync] GITHUB_TOKEN not configured. Skipping download.")
        return False
        
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{DB_FILE_PATH}"
    req = urllib.request.Request(url, headers=get_headers())
    
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode("utf-8"))
            content_b64 = data["content"]
            db_bytes = base64.b64decode(content_b64)
            
            # Write to DB_PATH
            os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
            with open(DB_PATH, "wb") as f:
                f.write(db_bytes)
            print("[GitHub Sync] Successfully downloaded database from GitHub.")
            return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("[GitHub Sync] Database file not found on GitHub. Will initialize a new one.")
        else:
            print(f"[GitHub Sync] Failed to download database: HTTP {e.code} - {e.reason}")
        return False
    except Exception as e:
        print("[GitHub Sync] Error downloading database:", e)
        return False

def upload_db():
    if not GITHUB_TOKEN:
        return False
        
    if not os.path.exists(DB_PATH):
        return False
        
    # Prevent concurrent uploads using thread lock
    if not upload_lock.acquire(blocking=False):
        print("[GitHub Sync] Upload already in progress. Skipping duplicate push.")
        return False
        
    try:
        url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{DB_FILE_PATH}"
        
        # 1. Fetch current SHA of the file if it exists
        sha = None
        req_get = urllib.request.Request(url, headers=get_headers())
        try:
            with urllib.request.urlopen(req_get) as response:
                data = json.loads(response.read().decode("utf-8"))
                sha = data["sha"]
        except Exception:
            pass # File might not exist on GitHub yet
            
        # 2. Read local database bytes and encode to base64
        with open(DB_PATH, "rb") as f:
            db_bytes = f.read()
        content_b64 = base64.b64encode(db_bytes).decode("utf-8")
        
        payload = {
            "message": "chore(db): Update traffic compliance database [skip ci]",
            "content": content_b64
        }
        if sha:
            payload["sha"] = sha
            
        data_json = json.dumps(payload).encode("utf-8")
        req_put = urllib.request.Request(url, data=data_json, headers=get_headers(), method="PUT")
        
        with urllib.request.urlopen(req_put) as response:
            print("[GitHub Sync] Successfully uploaded database to GitHub.")
            return True
    except Exception as e:
        print("[GitHub Sync] Error uploading database:", e)
        return False
    finally:
        upload_lock.release()

def upload_db_async():
    if not GITHUB_TOKEN:
        return
    thread = threading.Thread(target=upload_db)
    thread.daemon = True
    thread.start()
