from database.database import get_db_connection
from services.behaviour.behaviour_service import process_telemetry_compliance

def start_trip(trip_id, mode, start_time):
    """
    Initializes a new trip in the SQLite database with 100 safety score.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO trips (
            id, mode, start_time, end_time, duration_seconds, distance_km,
            avg_speed, max_speed, speed_compliance_pct, phone_free_pct,
            overspeed_count, phone_use_count, nudge_count, safety_score, points_earned
        ) VALUES (?, ?, ?, NULL, 0, 0.0, 0.0, 0.0, 100.0, 100.0, 0, 0, 0, 100.0, 0)
    """, (trip_id, mode, start_time))
    conn.commit()
    conn.close()
    return {"status": "started", "trip_id": trip_id}

def log_telemetry_tick(trip_id, speed, speed_limit, phone_use, timestamp, latitude=None, longitude=None, source="telemetry"):
    """
    Saves a telemetry tick, performs safety compliance checks, updates
    the trip metrics in real-time, and returns nudge & risk events.
    """
    # 1. Run behaviour checks
    result = process_telemetry_compliance(trip_id, speed, speed_limit, phone_use, timestamp, source)
    risk_level = result["risk_level"]
    score_deduction = result["score_deduction"]
    events = result["events"]
    nudges = result["nudges"]
    
    # 2. Insert telemetry record
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO telemetry_records (trip_id, timestamp, speed, speed_limit, phone_use, latitude, longitude, risk_level)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (trip_id, timestamp, speed, speed_limit, int(phone_use), latitude, longitude, risk_level))
    
    # 3. Update trip stats
    cursor.execute("SELECT * FROM trips WHERE id = ?", (trip_id,))
    trip = cursor.fetchone()
    
    if trip:
        # Fetch all telemetry ticks for this trip to compute statistics
        cursor.execute("SELECT speed, speed_limit, phone_use FROM telemetry_records WHERE trip_id = ?", (trip_id,))
        records = cursor.fetchall()
        
        total_ticks = len(records)
        avg_speed = sum(r['speed'] for r in records) / total_ticks if total_ticks > 0 else speed
        max_speed = max(r['speed'] for r in records) if total_ticks > 0 else speed
        
        compliant_speed_ticks = sum(1 for r in records if r['speed'] <= r['speed_limit'])
        speed_compliance_pct = (compliant_speed_ticks / total_ticks * 100) if total_ticks > 0 else 100.0
        
        phone_free_ticks = sum(1 for r in records if not r['phone_use'])
        phone_free_pct = (phone_free_ticks / total_ticks * 100) if total_ticks > 0 else 100.0
        
        # Calculate event counts
        cursor.execute("SELECT COUNT(*) FROM events WHERE trip_id = ? AND event_type = 'OVERSPEED'", (trip_id,))
        overspeed_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM events WHERE trip_id = ? AND event_type = 'PHONE_USE'", (trip_id,))
        phone_use_count = cursor.fetchone()[0]
        
        nudge_count = trip['nudge_count'] + len(nudges)
        
        new_safety_score = max(0.0, float(trip['safety_score']) - score_deduction)
        
        # Approximate distance: 1 tick = 1 second. Distance in km = (speed in km/h) * (1 / 3600 h)
        duration_seconds = total_ticks
        added_distance = (speed / 3600.0)
        distance_km = float(trip['distance_km']) + added_distance
        
        cursor.execute("""
            UPDATE trips SET
                duration_seconds = ?,
                distance_km = ?,
                avg_speed = ?,
                max_speed = ?,
                speed_compliance_pct = ?,
                phone_free_pct = ?,
                overspeed_count = ?,
                phone_use_count = ?,
                nudge_count = ?,
                safety_score = ?
            WHERE id = ?
        """, (duration_seconds, distance_km, avg_speed, max_speed, speed_compliance_pct, phone_free_pct,
              overspeed_count, phone_use_count, nudge_count, new_safety_score, trip_id))
        
    conn.commit()
    conn.close()
    
    return {
        "risk_level": risk_level,
        "events": events,
        "nudges": nudges,
        "safety_score": new_safety_score if trip else 100.0
    }

def end_trip(trip_id, end_time):
    """
    Finalizes trip duration, awards points/streaks, and returns the final trip summary.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM trips WHERE id = ?", (trip_id,))
    trip = cursor.fetchone()
    
    if not trip:
        conn.close()
        return {"error": "Trip not found"}
        
    # Calculate points earned:
    # 0 points if safety score is under 51.
    # Otherwise, points are based on the safety index (score / 5) plus compliance bonuses:
    # +5 if speed compliance >= 90%
    # +5 if phone free >= 90%
    # +10 bonus if safety score == 100
    if trip['safety_score'] < 51.0:
        points_earned = 0
    else:
        points_earned = int(trip['safety_score'] / 5.0)
        if trip['speed_compliance_pct'] >= 90.0:
            points_earned += 5
        if trip['phone_free_pct'] >= 90.0:
            points_earned += 5
        if trip['safety_score'] >= 100.0:
            points_earned += 10
        
    cursor.execute("""
        UPDATE trips SET
            end_time = ?,
            points_earned = ?
        WHERE id = ?
    """, (end_time, points_earned, trip_id))
    
    # Update user's streak and pod reputation if trip was safe (safety_score >= 80)
    is_safe_trip = trip['safety_score'] >= 80.0
    
    # 1. Update streak
    cursor.execute("SELECT current_streak, longest_streak FROM streaks WHERE id = 1")
    streak_row = cursor.fetchone()
    current_streak = streak_row['current_streak']
    longest_streak = streak_row['longest_streak']
    
    if is_safe_trip:
        current_streak += 1
        if current_streak > longest_streak:
            longest_streak = current_streak
    else:
        current_streak = 0  # Broken streak due to unsafe trip
        
    cursor.execute("""
        UPDATE streaks SET
            current_streak = ?,
            longest_streak = ?,
            last_trip_date = ?
        WHERE id = 1
    """, (current_streak, longest_streak, end_time))
    
    # 2. Update user's weekly score and streak in the peer pod
    cursor.execute("SELECT weekly_score, contribution FROM peer_pods WHERE is_user = 1")
    user_pod = cursor.fetchone()
    if user_pod:
        # Pod Weekly Score is average of members. For user, update their weekly score contribution:
        # user weekly score is a rolling window of recent safety scores (e.g. this score + previous avg)
        # For simplicity, we can do: new weekly score = (prev * 4 + new_trip_score) / 5
        new_weekly = int((user_pod['weekly_score'] * 4 + trip['safety_score']) / 5)
        # points contribution = user points earned from the trip
        new_contrib = user_pod['contribution'] + points_earned
        
        cursor.execute("""
            UPDATE peer_pods SET
                weekly_score = ?,
                streak = ?,
                contribution = ?
            WHERE is_user = 1
        """, (new_weekly, current_streak, new_contrib))
        
    conn.commit()
    conn.close()
    
    return {
        "status": "completed",
        "trip": {
            "id": trip['id'],
            "mode": trip['mode'],
            "start_time": trip['start_time'],
            "end_time": end_time,
            "duration_seconds": trip['duration_seconds'],
            "distance_km": trip['distance_km'],
            "avg_speed": trip['avg_speed'],
            "max_speed": trip['max_speed'],
            "speed_compliance_pct": trip['speed_compliance_pct'],
            "phone_free_pct": trip['phone_free_pct'],
            "overspeed_count": trip['overspeed_count'],
            "phone_use_count": trip['phone_use_count'],
            "nudge_count": trip['nudge_count'],
            "safety_score": trip['safety_score'],
            "points_earned": points_earned
        },
        "streak": {
            "current_streak": current_streak,
            "longest_streak": longest_streak
        }
    }
