from database.database import get_db_connection

def get_trip_nudges(trip_id):
    """
    Returns all events that generated nudges for a given trip.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM events 
        WHERE trip_id = ? AND event_type IN ('OVERSPEED', 'PHONE_USE')
        ORDER BY timestamp ASC
    """, (trip_id,))
    rows = cursor.fetchall()
    conn.close()
    
    nudges = []
    for r in rows:
        if r['event_type'] == 'OVERSPEED':
            msg = "⚠️ Slow Down — You're currently above the configured speed limit. Please reduce your speed and stay safe."
            if r['severity'] == 'HIGH_RISK':
                msg = "🚨 Critical Speed — Speeding severely increases crash risk. Slow down immediately!"
            nudges.append({
                "timestamp": r["timestamp"],
                "type": r["event_type"],
                "severity": r["severity"],
                "message": msg
            })
        elif r['event_type'] == 'PHONE_USE':
            nudges.append({
                "timestamp": r["timestamp"],
                "type": r["event_type"],
                "severity": r["severity"],
                "message": "📱 Focus on the Road — Phone use while driving increases risk. Please put the phone away."
            })
    return nudges
