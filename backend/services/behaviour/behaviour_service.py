from services.config_service import get_settings
from database.database import get_db_connection

def evaluate_speed_level(speed, speed_limit, settings):
    """
    Evaluates speed compliance level based on configured thresholds.
    Returns: 'SAFE', 'WARNING', or 'HIGH_RISK'
    """
    if speed <= 0:
        return 'SAFE'
    
    excess = speed - speed_limit
    if excess >= settings.get('critical_threshold', 15):
        return 'HIGH_RISK'
    elif excess >= settings.get('warning_threshold', 5):
        return 'WARNING'
    else:
        return 'SAFE'

def process_telemetry_compliance(user_id, trip_id, speed, speed_limit, phone_use, timestamp, source="telemetry"):
    """
    Core behaviour & risk engine.
    Analyzes current telemetry tick, detects event transitions, writes events/nudges,
    and returns risk assessment.
    """
    settings = get_settings(user_id)
    current_speed_level = evaluate_speed_level(speed, speed_limit, settings)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Fetch previous telemetry to detect transitions
    cursor.execute("""
        SELECT speed, speed_limit, phone_use, risk_level 
        from telemetry_records 
        WHERE trip_id = ? 
        ORDER BY id DESC LIMIT 1
    """, (trip_id,))
    prev_record = cursor.fetchone()
    
    prev_speed_level = 'SAFE'
    prev_phone_use = False
    if prev_record:
        prev_speed_level = prev_record['risk_level']
        prev_phone_use = bool(prev_record['phone_use'])
    
    events_triggered = []
    nudges_triggered = []
    
    # 2. Speed Event Transition Detection
    if current_speed_level != prev_speed_level:
        if current_speed_level == 'WARNING' and prev_speed_level == 'SAFE':
            events_triggered.append({
                "event_type": "OVERSPEED",
                "severity": "WARNING",
                "speed": speed,
                "speed_limit": speed_limit,
                "timestamp": timestamp,
                "source": source
            })
            nudges_triggered.append({
                "type": "SPEED_WARNING",
                "message": "⚠️ Slow Down — You're currently above the configured speed limit. Please reduce your speed and stay safe."
            })
        elif current_speed_level == 'HIGH_RISK':
            events_triggered.append({
                "event_type": "OVERSPEED",
                "severity": "HIGH_RISK",
                "speed": speed,
                "speed_limit": speed_limit,
                "timestamp": timestamp,
                "source": source
            })
            nudges_triggered.append({
                "type": "SPEED_CRITICAL",
                "message": "🚨 Critical Speed — Speeding severely increases crash risk. Slow down immediately!"
            })
        elif current_speed_level == 'SAFE' and prev_speed_level in ('WARNING', 'HIGH_RISK'):
            events_triggered.append({
                "event_type": "SAFE_DRIVING",
                "severity": "SAFE",
                "speed": speed,
                "speed_limit": speed_limit,
                "timestamp": timestamp,
                "source": source
            })
    
    # 3. Phone Event Transition Detection
    if phone_use and not prev_phone_use:
        events_triggered.append({
            "event_type": "PHONE_USE",
            "severity": "HIGH_RISK",
            "speed": speed,
            "speed_limit": speed_limit,
            "timestamp": timestamp,
            "source": source
        })
        nudges_triggered.append({
            "type": "PHONE_WARNING",
            "message": "📱 Focus on the Road — Phone use while driving increases risk. Please put the phone away."
        })
    elif not phone_use and prev_phone_use:
        events_triggered.append({
            "event_type": "SAFE_DRIVING",
            "severity": "SAFE",
            "speed": speed,
            "speed_limit": speed_limit,
            "timestamp": timestamp,
            "source": source
        })

    # 4. Save events and nudges to database
    score_deduction = 0
    for ev in events_triggered:
        cursor.execute("""
            INSERT INTO events (trip_id, event_type, severity, speed, speed_limit, timestamp, source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (trip_id, ev['event_type'], ev['severity'], ev['speed'], ev['speed_limit'], ev['timestamp'], ev['source']))
        
        # Calculate deduction
        if ev['event_type'] == 'OVERSPEED':
            if ev['severity'] == 'WARNING':
                score_deduction += settings.get('weight_minor_overspeed', 5)
            elif ev['severity'] == 'HIGH_RISK':
                score_deduction += settings.get('weight_severe_overspeed', 10)
        elif ev['event_type'] == 'PHONE_USE':
            score_deduction += settings.get('weight_phone_use', 10)
            
    conn.commit()
    conn.close()
    
    # Determine cumulative current risk
    overall_risk = 'SAFE'
    if current_speed_level == 'HIGH_RISK' or phone_use:
        overall_risk = 'HIGH_RISK'
    elif current_speed_level == 'WARNING':
        overall_risk = 'WARNING'
        
    return {
        "risk_level": overall_risk,
        "events": events_triggered,
        "nudges": nudges_triggered,
        "score_deduction": score_deduction
    }
