from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from database.database import get_db_connection

# Service imports
import services.config_service as config_svc
import services.telemetry.telemetry_service as telemetry_svc
import services.nudges.nudge_service as nudge_svc
import services.rewards.reward_service as reward_svc
import services.streaks.streak_service as streak_svc
import services.peer_pods.peer_pod_service as peer_pod_svc
import services.analytics.analytics_service as analytics_svc

router = APIRouter()

# --- Request/Response Models ---
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

class RedeemRequest(BaseModel):
    reward_id: str

# --- Settings Routes ---
@router.get("/settings")
def get_settings():
    return config_svc.get_settings()

@router.post("/settings")
def update_settings(payload: SettingsUpdate):
    return config_svc.update_settings(payload.dict())

# --- Trip & Telemetry Routes ---
@router.post("/trips/start")
def start_trip(payload: TripStartRequest):
    return telemetry_svc.start_trip(payload.trip_id, payload.mode, payload.start_time)

@router.post("/trips/tick")
def process_tick(payload: TelemetryTickRequest):
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
def end_trip(payload: TripEndRequest):
    result = telemetry_svc.end_trip(payload.trip_id, payload.end_time)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@router.get("/trips")
def list_trips(sort_by: Optional[str] = "Latest"):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Map sort_by parameter
    order_clause = "start_time DESC"
    if sort_by == "Highest Safety Score":
        order_clause = "safety_score DESC"
    elif sort_by == "Lowest Safety Score":
        order_clause = "safety_score ASC"
    elif sort_by == "Most Risk Events":
        order_clause = "(overspeed_count + phone_use_count) DESC"
    elif sort_by == "Longest Trip":
        order_clause = "distance_km DESC"
        
    cursor.execute(f"SELECT * FROM trips WHERE end_time IS NOT NULL ORDER BY {order_clause}")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.get("/trips/{trip_id}")
def get_trip(trip_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trips WHERE id = ?", (trip_id,))
    trip = cursor.fetchone()
    conn.close()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return dict(trip)

@router.delete("/trips/{trip_id}")
def delete_trip(trip_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted"}

@router.get("/trips/{trip_id}/telemetry")
def get_trip_telemetry(trip_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM telemetry_records WHERE trip_id = ? ORDER BY id ASC", (trip_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.get("/trips/{trip_id}/events")
def get_trip_events(trip_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events WHERE trip_id = ? ORDER BY timestamp ASC", (trip_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@router.get("/trips/{trip_id}/nudges")
def get_trip_nudges_list(trip_id: str):
    return nudge_svc.get_trip_nudges(trip_id)

# --- Gamification Routes ---
@router.get("/streaks")
def get_streaks():
    return streak_svc.get_streak_summary()

@router.get("/rewards")
def get_rewards():
    summary = reward_svc.get_points_summary()
    catalog = reward_svc.get_rewards_catalog()
    return {
        "points": summary,
        "catalog": catalog
    }

@router.post("/rewards/redeem")
def redeem_reward(payload: RedeemRequest):
    result = reward_svc.redeem_reward(payload.reward_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result

@router.get("/rewards/history")
def get_rewards_history():
    return reward_svc.get_redemption_history()

@router.get("/badges")
def get_badges():
    return reward_svc.get_badges()

@router.post("/self-report")
def self_report(payload: SelfReportRequest):
    return reward_svc.log_self_reported_event(payload.event_type, payload.description, payload.timestamp)

# --- Social Pod Routes ---
@router.get("/peer-pod")
def get_peer_pod():
    return peer_pod_svc.get_pod_details()

# --- Analytics Routes ---
@router.get("/analytics")
def get_analytics(time_filter: Optional[str] = "30 Days"):
    return analytics_svc.get_analytics_summary(time_filter)

# --- Global Events Feed ---
@router.get("/events")
def get_global_events():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events ORDER BY timestamp DESC LIMIT 30")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
