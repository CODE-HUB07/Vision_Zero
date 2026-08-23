import os
import sqlite3

if os.environ.get("VERCEL"):
    DB_PATH = "/tmp/traffic_compliance.db"
else:
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "traffic_compliance.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Settings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        id INTEGER PRIMARY KEY,
        warning_threshold INTEGER,
        critical_threshold INTEGER,
        weight_minor_overspeed INTEGER,
        weight_severe_overspeed INTEGER,
        weight_phone_use INTEGER,
        privacy_telemetry_on BOOLEAN,
        privacy_location_minimal BOOLEAN,
        privacy_data_retention_days INTEGER,
        privacy_sharing_on BOOLEAN,
        parent_email TEXT
    )
    """)

    # Attempt to alter existing table to add parent_email (for backwards compatibility)
    try:
        cursor.execute("ALTER TABLE settings ADD COLUMN parent_email TEXT")
    except sqlite3.OperationalError:
        pass # Column likely already exists
        
    # 2. Trips table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trips (
        id TEXT PRIMARY KEY,
        mode TEXT,
        start_time TEXT,
        end_time TEXT,
        duration_seconds INTEGER,
        distance_km REAL,
        avg_speed REAL,
        max_speed REAL,
        speed_compliance_pct REAL,
        phone_free_pct REAL,
        overspeed_count INTEGER,
        phone_use_count INTEGER,
        nudge_count INTEGER,
        safety_score REAL,
        points_earned INTEGER
    )
    """)

    # 3. Telemetry records table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS telemetry_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trip_id TEXT,
        timestamp TEXT,
        speed REAL,
        speed_limit REAL,
        phone_use BOOLEAN,
        latitude REAL,
        longitude REAL,
        risk_level TEXT,
        FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE
    )
    """)

    # 4. Events table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trip_id TEXT,
        event_type TEXT,
        severity TEXT,
        speed REAL,
        speed_limit REAL,
        timestamp TEXT,
        source TEXT,
        FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE
    )
    """)

    # 5. Streaks table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS streaks (
        id INTEGER PRIMARY KEY DEFAULT 1,
        current_streak INTEGER,
        longest_streak INTEGER,
        last_trip_date TEXT
    )
    """)

    # 6. Rewards table (redemptions)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_rewards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reward_id TEXT,
        name TEXT,
        cost_points INTEGER,
        redeemed_at TEXT,
        status TEXT
    )
    """)

    # 7. Peer Pods table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS peer_pods (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pod_name TEXT,
        member_name TEXT,
        weekly_score INTEGER,
        streak INTEGER,
        contribution INTEGER,
        is_user BOOLEAN
    )
    """)

    conn.commit()

    # Seed default settings if empty
    cursor.execute("SELECT COUNT(*) FROM settings")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO settings (
            id, warning_threshold, critical_threshold, weight_minor_overspeed,
            weight_severe_overspeed, weight_phone_use, privacy_telemetry_on,
            privacy_location_minimal, privacy_data_retention_days, privacy_sharing_on,
            parent_email
        ) VALUES (1, 5, 15, 5, 10, 10, 1, 1, 30, 1, '')
        """)

    # Seed default streak if empty
    cursor.execute("SELECT COUNT(*) FROM streaks")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO streaks (id, current_streak, longest_streak, last_trip_date)
        VALUES (1, 0, 0, NULL)
        """)

    # Seed default peer pod data if empty
    cursor.execute("SELECT COUNT(*) FROM peer_pods")
    if cursor.fetchone()[0] == 0:
        pod_members = [
            ("ROAD GUARDIANS", "Alex (You)", 100, 0, 0, 1),
            ("ROAD GUARDIANS", "Sarah", 98, 14, 15, 0),
            ("ROAD GUARDIANS", "David", 92, 5, 10, 0),
            ("ROAD GUARDIANS", "Emma", 88, 9, 8, 0),
            ("ROAD GUARDIANS", "James", 95, 12, 12, 0)
        ]
        cursor.executemany("""
        INSERT INTO peer_pods (pod_name, member_name, weekly_score, streak, contribution, is_user)
        VALUES (?, ?, ?, ?, ?, ?)
        """, pod_members)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)
