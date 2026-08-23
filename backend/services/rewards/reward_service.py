from database.database import get_db_connection
from datetime import datetime

REWARDS_CATALOG = [
    {"id": "fuel_discount", "name": "Prototype Fuel Discount (10% off)", "cost": 100, "description": "Get a 10% discount on your next fuel purchase at partner stations."},
    {"id": "mobile_data", "name": "Prototype Mobile Data Boost (5GB)", "cost": 250, "description": "5GB high-speed mobile data voucher valid for 30 days."},
    {"id": "cashback", "name": "Prototype Cashback Reward ($25)", "cost": 500, "description": "$25 cashback credited to your registered wallet/bank account."},
    {"id": "insurance_benefit", "name": "Prototype Insurance Premium Benefit", "cost": 1000, "description": "Reduce your monthly car insurance premium by 15%."}
]

def get_points_summary():
    """
    Computes total points earned, points spent, and current balance.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get user's total points contribution from peer_pods (includes trips and self-reporting)
    cursor.execute("SELECT contribution FROM peer_pods WHERE is_user = 1")
    row = cursor.fetchone()
    total_earned = row['contribution'] if row else 0
    
    # Points spent on rewards
    cursor.execute("SELECT SUM(cost_points) FROM user_rewards")
    total_spent = cursor.fetchone()[0] or 0
    
    conn.close()
    
    return {
        "total_earned": total_earned,
        "total_spent": total_spent,
        "balance": max(0, total_earned - total_spent)
    }

def get_rewards_catalog():
    return REWARDS_CATALOG

def redeem_reward(reward_id):
    """
    Deducts points if balance is sufficient, and logs redemption.
    """
    reward = next((r for r in REWARDS_CATALOG if r["id"] == reward_id), None)
    if not reward:
        return {"error": "Reward not found"}
        
    summary = get_points_summary()
    if summary["balance"] < reward["cost"]:
        return {"error": f"Insufficient points. You need {reward['cost']} points but only have {summary['balance']}."}
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user_rewards (reward_id, name, cost_points, redeemed_at, status)
        VALUES (?, ?, ?, ?, ?)
    """, (reward["id"], reward["name"], reward["cost"], datetime.now().isoformat(), "Active"))
    
    conn.commit()
    conn.close()
    
    return {"status": "success", "reward": reward}

def get_redemption_history():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_rewards ORDER BY redeemed_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_badges():
    """
    Dynamically checks which badges the user has unlocked based on real DB values.
    Badges:
    - Road Guardian: unlocked if user has safety score of 100 on at least 3 trips
    - Safe Streak: unlocked if current streak >= 5
    - Phone-Free Driver: unlocked if user has 100% phone-free driving on any trip
    - Speed Discipline: unlocked if user has 100% speed compliance on any trip
    - Consistency Champion: unlocked if completed at least 5 total trips
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Total Completed Trips
    cursor.execute("SELECT COUNT(*) FROM trips WHERE end_time IS NOT NULL")
    completed_trips = cursor.fetchone()[0]
    
    # 2. Perfect 100 score trips
    cursor.execute("SELECT COUNT(*) FROM trips WHERE safety_score = 100.0 AND end_time IS NOT NULL")
    perfect_trips = cursor.fetchone()[0]
    
    # 3. Safe Streak info
    cursor.execute("SELECT current_streak, longest_streak FROM streaks WHERE id = 1")
    streak_row = cursor.fetchone()
    current_streak = streak_row['current_streak'] if streak_row else 0
    longest_streak = streak_row['longest_streak'] if streak_row else 0
    
    # 4. Perfect Phone Free Trip
    cursor.execute("SELECT COUNT(*) FROM trips WHERE phone_free_pct = 100.0 AND end_time IS NOT NULL")
    perfect_phone_trips = cursor.fetchone()[0]
    
    # 5. Perfect Speed Compliance Trip
    cursor.execute("SELECT COUNT(*) FROM trips WHERE speed_compliance_pct = 100.0 AND end_time IS NOT NULL")
    perfect_speed_trips = cursor.fetchone()[0]
    
    conn.close()
    
    badges_list = [
        {
            "id": "road_guardian",
            "name": "🏆 Road Guardian",
            "description": "Unlock a safety score of 100 on 3 trips.",
            "unlocked": perfect_trips >= 3,
            "progress": f"{perfect_trips}/3 Perfect Trips"
        },
        {
            "id": "safe_streak",
            "name": "🔥 Safe Streak Hero",
            "description": "Maintain a streak of 5 safe driving trips.",
            "unlocked": longest_streak >= 5,
            "progress": f"Longest Streak: {longest_streak}/5"
        },
        {
            "id": "phone_free",
            "name": "📱 Phone-Free Champ",
            "description": "Complete a trip with 100% phone-free driving.",
            "unlocked": perfect_phone_trips >= 1,
            "progress": "Unlocked" if perfect_phone_trips >= 1 else "Not Unlocked"
        },
        {
            "id": "speed_discipline",
            "name": "🚦 Speed Discipline",
            "description": "Complete a trip with 100% speed limit compliance.",
            "unlocked": perfect_speed_trips >= 1,
            "progress": "Unlocked" if perfect_speed_trips >= 1 else "Not Unlocked"
        },
        {
            "id": "consistency_champion",
            "name": "⭐ Consistency Champion",
            "description": "Complete 5 trips of any compliance level.",
            "unlocked": completed_trips >= 5,
            "progress": f"{completed_trips}/5 trips"
        }
    ]
    return badges_list

def log_self_reported_event(event_type, description, timestamp):
    """
    Logs a self-reported compliance deviation or event.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Map event categories to severity
    severity = "WARNING"
    if event_type == "I used my phone" or event_type == "I exceeded the speed limit":
        severity = "WARNING"
    elif event_type == "I completed a safe trip":
        severity = "SAFE"
    else:
        severity = "INFO"
        
    cursor.execute("""
        INSERT INTO events (trip_id, event_type, severity, speed, speed_limit, timestamp, source)
        VALUES (NULL, ?, ?, 0.0, 0.0, ?, ?)
    """, (f"SELF_REPORTED_EVENT: {event_type} - {description}", severity, timestamp, "self_report"))
    
    # Deduct a light penalty or award a small point for honesty
    # Let's say if they report a violation they lose 2 points, but reporting a safe trip awards 2 points
    points_change = 0
    if severity == "WARNING":
        points_change = -5  # minor penalty for violation
    elif severity == "SAFE":
        points_change = 2   # small reward for logging safe behaviour
        
    # Since self-reports don't have trips, we can create a placeholder trip if needed, or adjust points directly.
    # Actually, we can log self-reports to trip history as a dummy/manual log, or just let it adjust the pod contribution.
    # Let's deduct/award points to the user's pod contribution.
    if points_change != 0:
        cursor.execute("UPDATE peer_pods SET contribution = MAX(0, contribution + ?) WHERE is_user = 1", (points_change,))
        
    conn.commit()
    conn.close()
    return {"status": "success", "points_change": points_change}
