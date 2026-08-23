import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from database.database import get_db_connection

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
try:
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587") or "587")
except ValueError:
    SMTP_PORT = 587
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "safeguard-compliance@example.com")

def send_email(to_email: str, subject: str, body: str) -> bool:
    """Delivers an email message via SMTP. Returns True on success, False on failure."""
    if not SMTP_USER or not SMTP_PASS:
        # Offline or missing SMTP configuration - fail gracefully so we queue the message
        return False
        
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_FROM
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=5)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_FROM, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print("SMTP Send Failed:", e)
        return False

def trigger_alert(user_id: int, trip_id: str, event_type: str, speed: float = None, limit: float = None, latitude: float = None, longitude: float = None):
    """Triggers a parental notification if configured, subject to a once-per-trip cooldown."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Fetch user settings
    cursor.execute("""
        SELECT name, guardian_email, guardian_enabled FROM users WHERE id = ?
    """, (user_id,))
    user = cursor.fetchone()
    
    if not user or not user['guardian_enabled'] or not user['guardian_email']:
        conn.close()
        return
        
    guardian_email = user['guardian_email'].strip()
    if not guardian_email:
        conn.close()
        return
        
    # 2. Check Cooldown: Max one overspeed and one phone-use alert per trip
    cursor.execute("""
        SELECT COUNT(*) FROM notifications
        WHERE user_id = ? AND trip_id = ? AND event_type = ?
    """, (user_id, trip_id, event_type))
    if cursor.fetchone()[0] > 0:
        conn.close()
        return # Already alerted for this event type on this trip
        
    # 3. Construct email
    driver_name = user['name']
    timestamp = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    
    subject = f"SafeGuard Alert: {driver_name} - {event_type} Registered"
    
    lat = latitude if latitude is not None else 12.9716
    lon = longitude if longitude is not None else 77.5946
    maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
    
    if event_type == "OVERSPEED":
        details = f"Recorded Speed: {speed} km/h (configured speed limit: {limit} km/h)"
    else:
        details = "Distraction Event: Driver was observed using a mobile device while in motion."
        
    body = f"""SafeGuard Automatic Compliance Alert

Driver: {driver_name}
Event Type: {event_type}
Timestamp: {timestamp}
Details: {details}
Demo Location: {lat}, {lon}
Google Maps Link: {maps_url}

This is a routine accountability alert sent by the driver's onboard compliance engine. No immediate action is required.
"""

    # 4. Attempt delivery
    sent = send_email(guardian_email, subject, body)
    status = "SENT" if sent else "QUEUED"
    
    # 5. Insert notification record
    cursor.execute("""
        INSERT INTO notifications (user_id, trip_id, event_type, recipient, content, status, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, trip_id, event_type, guardian_email, body, status, datetime.now().isoformat()))
    
    conn.commit()
    conn.close()

def retry_queued_notifications(user_id: int) -> dict:
    """Attempts to resend all previously queued/failed notifications for the user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, recipient, event_type, content FROM notifications
        WHERE user_id = ? AND status = 'QUEUED'
    """, (user_id,))
    
    queued = [dict(r) for r in cursor.fetchall()]
    
    success_count = 0
    for q in queued:
        subject = f"SafeGuard Alert: Retry - {q['event_type']}"
        sent = send_email(q['recipient'], subject, q['content'])
        if sent:
            cursor.execute("UPDATE notifications SET status = 'SENT' WHERE id = ?", (q['id'],))
            success_count += 1
            
    conn.commit()
    conn.close()
    
    return {"retried": len(queued), "success": success_count}

def get_notification_history(user_id: int) -> list:
    """Retrieves all notification attempts for the user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, trip_id, event_type, recipient, status, timestamp
        FROM notifications
        WHERE user_id = ?
        ORDER BY timestamp DESC
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
