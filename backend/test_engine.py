import os
import sys
from database.database import init_db, get_db_connection

# Set python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.behaviour.behaviour_service import evaluate_speed_level, process_telemetry_compliance
from services.config_service import get_settings

def run_tests():
    print("=== Initializing Test DB ===")
    init_db()
    
    # Clear tables to ensure sandboxed test execution
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM trips")
    cursor.execute("DELETE FROM telemetry_records")
    cursor.execute("DELETE FROM events")
    cursor.execute("DELETE FROM user_rewards")
    cursor.execute("UPDATE streaks SET current_streak=0, longest_streak=0, last_trip_date=NULL WHERE id=1")
    conn.commit()
    conn.close()
    
    settings = get_settings(1)
    print("Current Settings in DB:", settings)
    
    print("\n=== Test 1: Speed compliance evaluations ===")
    # 35 vs 40 limit -> SAFE
    level_safe = evaluate_speed_level(35, 40, settings)
    print(f"Speed 35 km/h, Limit 40 km/h -> Level: {level_safe} (Expected: SAFE)")
    assert level_safe == 'SAFE'
    
    # 47 vs 40 limit -> WARNING (+7 over limit)
    level_warn = evaluate_speed_level(47, 40, settings)
    print(f"Speed 47 km/h, Limit 40 km/h -> Level: {level_warn} (Expected: WARNING)")
    assert level_warn == 'WARNING'
    
    # 57 vs 40 limit -> HIGH_RISK (+17 over limit)
    level_crit = evaluate_speed_level(57, 40, settings)
    print(f"Speed 57 km/h, Limit 40 km/h -> Level: {level_crit} (Expected: HIGH_RISK)")
    assert level_crit == 'HIGH_RISK'
    
    print("\n=== Test 2: Process Telemetry Compliances ===")
    trip_id = "test_trip_1"
    
    # First tick: Safe
    res1 = process_telemetry_compliance(1, trip_id, 35, 40, False, "10:00:00")
    print("Safe driving tick response:", res1)
    assert res1["risk_level"] == "SAFE"
    assert len(res1["events"]) == 0
    
    # Let's save a fake telemetry record to mock transition database history
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO telemetry_records (trip_id, timestamp, speed, speed_limit, phone_use, risk_level)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (trip_id, '10:00:00', 35, 40, 0, 'SAFE'))
    conn.commit()
    
    # Second tick: Overspeed (+7 km/h) -> WARNING
    res2 = process_telemetry_compliance(1, trip_id, 47, 40, False, "10:00:01")
    print("Overspeed warning tick response:", res2)
    assert res2["risk_level"] == "WARNING"
    assert len(res2["events"]) == 1
    assert res2["events"][0]["event_type"] == "OVERSPEED"
    assert res2["events"][0]["severity"] == "WARNING"
    
    cursor.execute("""
        INSERT INTO telemetry_records (trip_id, timestamp, speed, speed_limit, phone_use, risk_level)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (trip_id, '10:00:01', 47, 40, 0, 'WARNING'))
    conn.commit()
    
    # Third tick: Phone Use -> HIGH_RISK
    res3 = process_telemetry_compliance(1, trip_id, 35, 40, True, "10:00:02")
    print("Phone use tick response:", res3)
    assert res3["risk_level"] == "HIGH_RISK"
    assert len(res3["events"]) == 2
    event_types = [e["event_type"] for e in res3["events"]]
    assert "PHONE_USE" in event_types
    assert "SAFE_DRIVING" in event_types
    
    conn.close()
    print("\n=== ALL TESTS PASSED! ===")

if __name__ == "__main__":
    run_tests()
