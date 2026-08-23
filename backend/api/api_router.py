import re
from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional, List
from database.database import get_db_connection

# Service imports
import services.config_service as config_svc
import services.telemetry.telemetry_service as telemetry_svc
import services.nudges.nudge_service as nudge_svc
import services.rewards.reward_service as reward_svc
import services.streaks.streak_service as streak_svc
import services.peer_pods.peer_pod_service as peer_pod_svc
import services.analytics.analytics_service as analytics_svc
import services.auth_service as auth_svc
import services.notification_service as notification_svc

router = APIRouter()

# --- Helpers ---
def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@]+@[^@]+\.[^@]+$", email))

# --- Authentication Dependency ---
def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication token required.")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token scheme.")
    token = authorization.split(" ")[1]
    
    user = auth_svc.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Session expired or invalid. Please log in again.")
    return user

# --- Request/Response Models ---
class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class ProfileUpdateRequest(BaseModel):
    name: str
    password: Optional[str] = None
    old_password: Optional[str] = None
    guardian_email: Optional[str] = ""
    guardian_enabled: Optional[bool] = False

class SettingsUpdate(BaseModel):
    warning_threshold: int
    critical_threshold: int
    weight_minor_overspeed: int
    weight_severe_overspeed: int
    weight_phone_use: int
    privacy_telemetry_on: bool
    privacy_location_minimal: bool
    privacy_data_retention_days: int
    privacy_sharing_on: bool
    parent_email: Optional[str] = ""

class TripStartRequest(BaseModel):
    trip_id: str
    mode: str
    start_time: str

class TelemetryTickRequest(BaseModel):
    trip_id: str
    speed: float
    speed_limit: float
    phone_use: bool
    timestamp: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    source: Optional[str] = "telemetry"

class TripEndRequest(BaseModel):
    trip_id: str
    end_time: str

class SelfReportRequest(BaseModel):
    event_type: str
    description: str
    timestamp: str

class NotificationStatusUpdate(BaseModel):
    trip_id: str
    event_type: str
    status: str

class RedeemRequest(BaseModel):
    reward_id: str

# --- Auth Routes ---
@router.post("/auth/register")
def register(payload: RegisterRequest):
    email_clean = payload.email.strip().lower()
    name_clean = payload.name.strip()
    
    if not name_clean or not email_clean or not payload.password:
        raise HTTPException(status_code=400, detail="All fields are required.")
    if not is_valid_email(email_clean):
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")
    if len(payload.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check duplicate email
    cursor.execute("SELECT id FROM users WHERE email = ?", (email_clean,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="An account with this email address already exists.")
        
    # Hash password and store
    hashed = auth_svc.hash_password(payload.password)
    cursor.execute("""
        INSERT INTO users (name, email, hashed_password, guardian_email, guardian_enabled)
        VALUES (?, ?, ?, '', 0)
    """, (name_clean, email_clean, hashed))
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # Seed default stats and pod contributions dynamically
    token = auth_svc.create_session(user_id, name_clean, email_clean)
    
    return {
        "status": "registered",
        "token": token,
        "user": {"id": user_id, "name": name_clean, "email": email_clean}
    }

@router.post("/auth/login")
def login(payload: LoginRequest):
    email_clean = payload.email.strip().lower()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email_clean,))
    user = cursor.fetchone()
    
    if not user:
        from database.github_sync import download_db
        print(f"[GitHub Sync] User email {email_clean} not found during login. Syncing...")
        conn.close()
        download_db()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email_clean,))
        user = cursor.fetchone()
        
    conn.close()
    
    if not user or not auth_svc.verify_password(payload.password, user['hashed_password']):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
        
    token = auth_svc.create_session(user['id'], user['name'], user['email'])
    
    return {
        "status": "logged_in",
        "token": token,
        "user": {"id": user['id'], "name": user['name'], "email": user['email']}
    }

@router.post("/auth/logout")
def logout(authorization: Optional[str] = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        auth_svc.invalidate_session(token)
    return {"status": "logged_out"}

@router.get("/auth/me")
def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "id": current_user["id"],
        "name": current_user["name"],
        "email": current_user["email"],
        "guardian_email": current_user.get("guardian_email") or "",
        "guardian_enabled": bool(current_user.get("guardian_enabled")),
        "created_at": current_user.get("created_at")
    }

@router.post("/profile/update")
def update_profile(payload: ProfileUpdateRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user["id"]
    name_clean = payload.name.strip()
    g_email_clean = payload.guardian_email.strip() if payload.guardian_email else ""
    
    if not name_clean:
        raise HTTPException(status_code=400, detail="Name cannot be empty.")
    if g_email_clean and not is_valid_email(g_email_clean):
        raise HTTPException(status_code=400, detail="Please enter a valid guardian email address.")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Update Name and Guardian Settings
    cursor.execute("""
        UPDATE users 
        SET name = ?, guardian_email = ?, guardian_enabled = ?
        WHERE id = ?
    """, (name_clean, g_email_clean, int(payload.guardian_enabled), user_id))
    
    # 2. Update Password if specified
    if payload.password:
        if not payload.old_password:
            conn.close()
            raise HTTPException(status_code=400, detail="Old password is required to change password.")
            
        cursor.execute("SELECT hashed_password FROM users WHERE id = ?", (user_id,))
        stored_hash = cursor.fetchone()['hashed_password']
        
        if not auth_svc.verify_password(payload.old_password, stored_hash):
            conn.close()
            raise HTTPException(status_code=401, detail="Incorrect old password.")
            
        new_hashed = auth_svc.hash_password(payload.password)
        cursor.execute("UPDATE users SET hashed_password = ? WHERE id = ?", (new_hashed, user_id))
        
    conn.commit()
    conn.close()
    
    return {"status": "updated"}

# --- Settings Routes ---
@router.get("/settings")
def get_settings(current_user: dict = Depends(get_current_user)):
    return config_svc.get_settings(current_user["id"])

@router.post("/settings")
def update_settings(payload: SettingsUpdate, current_user: dict = Depends(get_current_user)):
    return config_svc.update_settings(current_user["id"], payload.dict())

# --- Trip & Telemetry Routes ---
@router.post("/trips/start")
def start_trip(payload: TripStartRequest, current_user: dict = Depends(get_current_user)):
    return telemetry_svc.start_trip(payload.trip_id, payload.mode, payload.start_time, current_user["id"])

@router.post("/trips/tick")
def process_tick(payload: TelemetryTickRequest, current_user: dict = Depends(get_current_user)):
    if payload.speed < 0:
         raise HTTPException(status_code=400, detail="Speed cannot be negative")
    if payload.speed_limit <= 0:
         raise HTTPException(status_code=400, detail="Speed limit must be greater than zero")
         
    return telemetry_svc.log_telemetry_tick(
        trip_id=payload.trip_id,
        speed=payload.speed,
        speed_limit=payload.speed_limit,
        phone_use=payload.phone_use,
        timestamp=payload.timestamp,
        latitude=payload.latitude,
        longitude=payload.longitude,
        source=payload.source
    )

@router.post("/trips/end")
def end_trip(payload: TripEndRequest, current_user: dict = Depends(get_current_user)):
    result = telemetry_svc.end_trip(payload.trip_id, payload.end_time)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@router.get("/trips")
def list_trips(sort_by: Optional[str] = "Latest", current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    order_clause = "start_time DESC"
    if sort_by == "Highest Safety Score":
        order_clause = "safety_score DESC"
    elif sort_by == "Lowest Safety Score":
        order_clause = "safety_score ASC"
    elif sort_by == "Most Risk Events":
        order_clause = "(overspeed_count + phone_use_count) DESC"
    elif sort_by == "Longest Trip":
        order_clause = "distance_km DESC"
        
    cursor.execute(f"""
        SELECT * FROM trips 
        WHERE end_time IS NOT NULL AND user_id = ? 
        ORDER BY {order_clause}
    """, (current_user["id"],))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.get("/trips/{trip_id}")
def get_trip(trip_id: str, current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trips WHERE id = ? AND user_id = ?", (trip_id, current_user["id"]))
    trip = cursor.fetchone()
    
    if not trip:
        from database.github_sync import download_db
        print(f"[GitHub Sync] Trip {trip_id} not found in get_trip. Syncing database...")
        conn.close()
        download_db()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trips WHERE id = ? AND user_id = ?", (trip_id, current_user["id"]))
        trip = cursor.fetchone()
        
    conn.close()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return dict(trip)

@router.delete("/trips/{trip_id}")
def delete_trip(trip_id: str, current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM trips WHERE id = ? AND user_id = ?", (trip_id, current_user["id"]))
    conn.commit()
    conn.close()
    return {"status": "deleted"}

@router.get("/trips/{trip_id}/telemetry")
def get_trip_telemetry(trip_id: str, current_user: dict = Depends(get_current_user)):
    # Verify trip ownership first
    get_trip(trip_id, current_user)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM telemetry_records WHERE trip_id = ? ORDER BY id ASC", (trip_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.get("/trips/{trip_id}/events")
def get_trip_events(trip_id: str, current_user: dict = Depends(get_current_user)):
    # Verify trip ownership first
    get_trip(trip_id, current_user)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events WHERE trip_id = ? ORDER BY timestamp ASC", (trip_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.get("/trips/{trip_id}/nudges")
def get_trip_nudges_list(trip_id: str, current_user: dict = Depends(get_current_user)):
    # Verify trip ownership first
    get_trip(trip_id, current_user)
    return nudge_svc.get_trip_nudges(trip_id)

# --- Gamification Routes ---
@router.get("/streaks")
def get_streaks(current_user: dict = Depends(get_current_user)):
    return streak_svc.get_streak_summary(current_user["id"])

@router.get("/rewards")
def get_rewards(current_user: dict = Depends(get_current_user)):
    summary = reward_svc.get_points_summary(current_user["id"])
    catalog = reward_svc.get_rewards_catalog()
    return {
        "points": summary,
        "catalog": catalog
    }

@router.post("/rewards/redeem")
def redeem_reward(payload: RedeemRequest, current_user: dict = Depends(get_current_user)):
    result = reward_svc.redeem_reward(current_user["id"], payload.reward_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@router.get("/rewards/history")
def get_rewards_history(current_user: dict = Depends(get_current_user)):
    return reward_svc.get_redemption_history(current_user["id"])

@router.get("/badges")
def get_badges(current_user: dict = Depends(get_current_user)):
    return reward_svc.get_badges(current_user["id"])

@router.post("/self-report")
def self_report(payload: SelfReportRequest, current_user: dict = Depends(get_current_user)):
    return reward_svc.log_self_reported_event(current_user["id"], payload.event_type, payload.description, payload.timestamp)

# --- Social Pod Routes ---
@router.get("/peer-pod")
def get_peer_pod(current_user: dict = Depends(get_current_user)):
    return peer_pod_svc.get_pod_details(current_user["id"])

# --- Analytics Routes ---
@router.get("/analytics")
def get_analytics(time_filter: Optional[str] = "30 Days", current_user: dict = Depends(get_current_user)):
    return analytics_svc.get_analytics_summary(current_user["id"], time_filter)

# --- Parental Notifications ---
@router.get("/notifications/history")
def get_notifications(current_user: dict = Depends(get_current_user)):
    return notification_svc.get_notification_history(current_user["id"])

@router.post("/notifications/retry")
def retry_notifications(current_user: dict = Depends(get_current_user)):
    return notification_svc.retry_queued_notifications(current_user["id"])

@router.post("/notifications/status")
def update_notification_status(payload: NotificationStatusUpdate, current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE notifications 
        SET status = ? 
        WHERE user_id = ? AND trip_id = ? AND event_type = ?
    """, (payload.status, current_user["id"], payload.trip_id, payload.event_type))
    conn.commit()
    conn.close()
    return {"status": "updated"}

# --- Scoped Events Feed ---
@router.get("/events")
def get_global_events(current_user: dict = Depends(get_current_user)):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM events 
        WHERE user_id = ? OR trip_id IN (SELECT id FROM trips WHERE user_id = ?)
        ORDER BY timestamp DESC LIMIT 30
    """, (current_user["id"], current_user["id"]))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
