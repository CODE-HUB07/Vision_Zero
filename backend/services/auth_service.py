import hashlib
import secrets
from datetime import datetime, timedelta
from database.database import get_db_connection

ITERATIONS = 100000

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
        # Constant-time comparison
        return secrets.compare_digest(check, hashed)
    except Exception:
        return False

def create_session(user_id: int) -> str:
    """Generates a secure session token valid for 30 days."""
    token = secrets.token_hex(32)
    expires_at = (datetime.utcnow() + timedelta(days=30)).isoformat()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO sessions (token, user_id, expires_at)
        VALUES (?, ?, ?)
    """, (token, user_id, expires_at))
    conn.commit()
    conn.close()
    
    return token

def invalidate_session(token: str):
    """Deletes a session token from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()

def get_user_by_token(token: str) -> dict:
    """Retrieves the user associated with a non-expired token."""
    conn = get_db_connection()
    cursor = conn.cursor()
    # Query sessions and active users
    cursor.execute("""
        SELECT users.* FROM sessions
        JOIN users ON sessions.user_id = users.id
        WHERE sessions.token = ? AND datetime(sessions.expires_at) > datetime('now')
    """, (token,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None
