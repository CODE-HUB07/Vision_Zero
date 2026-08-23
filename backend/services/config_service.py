from database.database import get_db_connection

def get_settings():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM settings WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return {
        "warning_threshold": 5,
        "critical_threshold": 15,
        "weight_minor_overspeed": 5,
        "weight_severe_overspeed": 10,
        "weight_phone_use": 10,
        "privacy_telemetry_on": True,
        "privacy_location_minimal": True,
        "privacy_data_retention_days": 30,
        "privacy_sharing_on": True,
        "parent_email": ""
    }

def update_settings(settings_dict):
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
    WHERE id = 1
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
        settings_dict.get("parent_email", "")
    ))
    conn.commit()
    conn.close()
    return get_settings()
