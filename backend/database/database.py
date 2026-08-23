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

    # 0. Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        hashed_password TEXT NOT NULL,
        guardian_email TEXT,
        guardian_enabled BOOLEAN DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Sessions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        expires_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    )
    """)

    # Notifications table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        trip_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        recipient TEXT NOT NULL,
        content TEXT NOT NULL,
        status TEXT NOT NULL,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
        FOREIGN KEY (trip_id) REFERENCES trips (id) ON DELETE CASCADE
    )
    """)

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

    # Apply user_id migrations to existing tables
    for table in ["settings", "trips", "streaks", "user_rewards", "peer_pods", "events"]:
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER")
        except sqlite3.OperationalError:
            pass

    conn.commit()

    # Seed default user if empty
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        import hashlib
        import secrets
        salt = secrets.token_hex(16)
        hashed = hashlib.pbkdf2_hmac('sha256', b'password', salt.encode('utf-8'), 100000).hex()
        stored = f"{salt}:{hashed}"
        cursor.execute("""
            INSERT INTO users (id, name, email, hashed_password, guardian_email, guardian_enabled)
            VALUES (1, 'Default Driver', 'driver@safeguard.com', ?, '', 0)
        """, (stored,))
        conn.commit()

    # Bind loose rows to the default user (id = 1)
    cursor.execute("UPDATE settings SET user_id = 1 WHERE user_id IS NULL")
    cursor.execute("UPDATE trips SET user_id = 1 WHERE user_id IS NULL")
    cursor.execute("UPDATE streaks SET user_id = 1 WHERE user_id IS NULL")
    cursor.execute("UPDATE user_rewards SET user_id = 1 WHERE user_id IS NULL")
    cursor.execute("UPDATE peer_pods SET user_id = 1 WHERE user_id IS NULL")
    cursor.execute("UPDATE events SET user_id = 1 WHERE user_id IS NULL")
    conn.commit()

    # Seed default settings for user 1 if empty
    cursor.execute("SELECT COUNT(*) FROM settings WHERE user_id = 1")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO settings (
            id, warning_threshold, critical_threshold, weight_minor_overspeed,
            weight_severe_overspeed, weight_phone_use, privacy_telemetry_on,
            privacy_location_minimal, privacy_data_retention_days, privacy_sharing_on,
            parent_email, user_id
        ) VALUES (1, 5, 15, 5, 10, 10, 1, 1, 30, 1, '', 1)
        """)

    # Seed default streak for user 1 if empty
    cursor.execute("SELECT COUNT(*) FROM streaks WHERE user_id = 1")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO streaks (id, current_streak, longest_streak, last_trip_date, user_id)
        VALUES (1, 0, 0, NULL, 1)
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
