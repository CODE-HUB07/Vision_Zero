from database.database import get_db_connection

def get_settings(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM settings WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if not row:
        cursor.execute("""
        INSERT INTO settings (
            warning_threshold, critical_threshold, weight_minor_overspeed,
            weight_severe_overspeed, weight_phone_use, privacy_telemetry_on,
            privacy_location_minimal, privacy_data_retention_days, privacy_sharing_on,
            parent_email, user_id
        ) VALUES (5, 15, 5, 10, 10, 1, 1, 30, 1, '', ?)
        """, (user_id,))
        conn.commit()
        cursor.execute("SELECT * FROM settings WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
    conn.close()
    return dict(row)

def update_settings(user_id: int, settings_dict: dict):
    # Dynamically seed settings first if missing
    get_settings(user_id)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    UPDATE settings SET
        warning_threshold = ?,
        critical_threshold = ?,
        weight_minor_overspeed = ?,
        weight_severe_overspeed = ?,
        weight_phone_use = ?,
        privacy_telemetry_on = ?,
        privacy_location_minimal = ?,
        privacy_data_retention_days = ?,
        privacy_sharing_on = ?,
        parent_email = ?
    WHERE user_id = ?
    """, (
        settings_dict.get("warning_threshold", 5),
        settings_dict.get("critical_threshold", 15),
        settings_dict.get("weight_minor_overspeed", 5),
        settings_dict.get("weight_severe_overspeed", 10),
        settings_dict.get("weight_phone_use", 10),
        int(settings_dict.get("privacy_telemetry_on", True)),
        int(settings_dict.get("privacy_location_minimal", True)),
        settings_dict.get("privacy_data_retention_days", 30),
        int(settings_dict.get("privacy_sharing_on", True)),
        settings_dict.get("parent_email", ""),
        user_id
    ))
    conn.commit()
    conn.close()
    return get_settings(user_id)
