import os
import hmac
import hashlib
import secrets
import json
import base64
import time
from datetime import datetime, timedelta
from database.database import get_db_connection

ITERATIONS = 100000
JWT_SECRET = os.environ.get("JWT_SECRET", "safeguard-super-secret-key-123456")

def hash_password(password: str) -> str:
    """Hashes a password using PBKDF2-HMAC-SHA256 with a unique salt."""
    salt = secrets.token_hex(16)
    pwd_bytes = password.encode('utf-8')
    salt_bytes = salt.encode('utf-8')
    hashed = hashlib.pbkdf2_hmac('sha256', pwd_bytes, salt_bytes, ITERATIONS).hex()
    return f"{salt}:{hashed}"

def verify_password(plain_password: str, stored_hash: str) -> bool:
    """Verifies a plain-text password against a stored salt:hash string."""
    try:
        salt, hashed = stored_hash.split(":")
        pwd_bytes = plain_password.encode('utf-8')
        salt_bytes = salt.encode('utf-8')
        check = hashlib.pbkdf2_hmac('sha256', pwd_bytes, salt_bytes, ITERATIONS).hex()
        return secrets.compare_digest(check, hashed)
    except Exception:
        return False

# --- Stateless JWT Helpers ---

def base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

def base64url_decode(data: str) -> bytes:
    padding = '=' * (4 - (len(data) % 4))
    return base64.urlsafe_b64decode(data + padding)

def create_jwt(payload: dict) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = base64url_encode(json.dumps(header).encode('utf-8'))
    payload_b64 = base64url_encode(json.dumps(payload).encode('utf-8'))
    
    signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
    signature = hmac.new(JWT_SECRET.encode('utf-8'), signing_input, hashlib.sha256).digest()
    signature_b64 = base64url_encode(signature)
    
    return f"{header_b64}.{payload_b64}.{signature_b64}"

def verify_jwt(token: str) -> dict:
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
            
        header_b64, payload_b64, signature_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
        expected_signature = hmac.new(JWT_SECRET.encode('utf-8'), signing_input, hashlib.sha256).digest()
        
        if not hmac.compare_digest(base64url_decode(signature_b64), expected_signature):
            return None
            
        payload = json.loads(base64url_decode(payload_b64).decode('utf-8'))
        
        if "exp" in payload and payload["exp"] < time.time():
            return None
            
        return payload
    except Exception:
        return None

# --- Session Functions ---

def create_session(user_id: int) -> str:
    """Generates a secure stateless JWT token valid for 30 days."""
    payload = {
        "user_id": user_id,
        "exp": int(time.time()) + 30 * 24 * 3600
    }
    return create_jwt(payload)

def invalidate_session(token: str):
    """Stateless sessions don't need deletion, handled on client-side."""
    pass

def get_user_by_token(token: str) -> dict:
    """Retrieves the user associated with a validated JWT token."""
    payload = verify_jwt(token)
    if not payload or "user_id" not in payload:
        return None
        
    user_id = payload["user_id"]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None
