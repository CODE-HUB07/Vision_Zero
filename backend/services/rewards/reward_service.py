from database.database import get_db_connection
from datetime import datetime

REWARDS_CATALOG = [
    {"id": "fuel_discount", "name": "Fuel Discount (10% off)", "cost": 100, "description": "Get a 10% discount on your next fuel purchase at partner stations."},
    {"id": "mobile_data", "name": "Mobile Data Boost (5GB)", "cost": 250, "description": "5GB high-speed mobile data voucher valid for 30 days."},
    {"id": "cashback", "name": "Cashback Reward ($25)", "cost": 500, "description": "$25 cashback credited to your registered wallet/bank account."},
    {"id": "insurance_benefit", "name": "Insurance Premium Benefit", "cost": 1000, "description": "Reduce your monthly car insurance premium by 15%."}
]

def get_points_summary(user_id: int):
    """
    Computes total points earned, points spent, and current balance for a user.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get user's total points contribution from peer_pods (includes trips and self-reporting)
    cursor.execute("SELECT contribution FROM peer_pods WHERE is_user = 1 AND user_id = ?", (user_id,))
    row = cursor.fetchone()
    
    if not row:
        # Seed default pod entry for user
        cursor.execute("SELECT name FROM users WHERE id = ?", (user_id,))
        user_row = cursor.fetchone()
        uname = user_row['name'] if user_row else "Driver"
        cursor.execute("""
            INSERT INTO peer_pods (pod_name, member_name, weekly_score, streak, contribution, is_user, user_id)
            VALUES ('ROAD GUARDIANS', ?, 100, 0, 0, 1, ?)
        """, (uname, user_id))
        conn.commit()
        total_earned = 0
    else:
        total_earned = row['contribution']
    
    # Points spent on rewards
    cursor.execute("SELECT SUM(cost_points) FROM user_rewards WHERE user_id = ?", (user_id,))
    total_spent = cursor.fetchone()[0] or 0
    
    conn.close()
    
    return {
        "total_earned": total_earned,
        "total_spent": total_spent,
        "balance": max(0, total_earned - total_spent)
    }

def get_rewards_catalog():
    return REWARDS_CATALOG

def redeem_reward(user_id: int, reward_id: str):
    """
    Deducts points if balance is sufficient, and logs redemption.
    """
    reward = next((r for r in REWARDS_CATALOG if r["id"] == reward_id), None)
    if not reward:
        return {"error": "Reward not found"}
        
    summary = get_points_summary(user_id)
    if summary["balance"] < reward["cost"]:
        return {"error": f"Insufficient points. You need {reward['cost']} points but only have {summary['balance']}."}
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user_rewards (reward_id, name, cost_points, redeemed_at, status, user_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (reward["id"], reward["name"], reward["cost"], datetime.now().isoformat(), "Active", user_id))
    
    conn.commit()
    conn.close()
    
    return {"status": "success", "reward": reward}

def get_redemption_history(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_rewards WHERE user_id = ? ORDER BY redeemed_at DESC", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_badges(user_id: int):
    """
    Dynamically checks which badges the user has unlocked based on real DB values.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Total Completed Trips
    cursor.execute("SELECT COUNT(*) FROM trips WHERE end_time IS NOT NULL AND user_id = ?", (user_id,))
    completed_trips = cursor.fetchone()[0]
    
    # 2. Perfect 100 score trips
    cursor.execute("SELECT COUNT(*) FROM trips WHERE safety_score = 100.0 AND end_time IS NOT NULL AND user_id = ?", (user_id,))
    perfect_trips = cursor.fetchone()[0]
    
    # 3. Safe Streak info
    cursor.execute("SELECT current_streak, longest_streak FROM streaks WHERE user_id = ?", (user_id,))
    streak_row = cursor.fetchone()
    current_streak = streak_row['current_streak'] if streak_row else 0
    longest_streak = streak_row['longest_streak'] if streak_row else 0
    
    # 4. Perfect Phone Free Trip
    cursor.execute("SELECT COUNT(*) FROM trips WHERE phone_free_pct = 100.0 AND end_time IS NOT NULL AND user_id = ?", (user_id,))
    perfect_phone_trips = cursor.fetchone()[0]
    
    # 5. Perfect Speed Compliance Trip
    cursor.execute("SELECT COUNT(*) FROM trips WHERE speed_compliance_pct = 100.0 AND end_time IS NOT NULL AND user_id = ?", (user_id,))
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

def log_self_reported_event(user_id: int, event_type: str, description: str, timestamp: str):
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
        INSERT INTO events (trip_id, event_type, severity, speed, speed_limit, timestamp, source, user_id)
        VALUES (NULL, ?, ?, 0.0, 0.0, ?, ?, ?)
    """, (f"SELF_REPORTED_EVENT: {event_type} - {description}", severity, timestamp, "self_report", user_id))
    
    # Deduct a light penalty or award a small point for honesty
    points_change = 0
    if severity == "WARNING":
        points_change = -5  # minor penalty for violation
    elif severity == "SAFE":
        points_change = 2   # small reward for logging safe behaviour
        
    # Seed user in peer pods if missing
    cursor.execute("SELECT COUNT(*) FROM peer_pods WHERE is_user = 1 AND user_id = ?", (user_id,))
    if cursor.fetchone()[0] == 0:
        cursor.execute("SELECT name FROM users WHERE id = ?", (user_id,))
        user_row = cursor.fetchone()
        uname = user_row['name'] if user_row else "Driver"
        cursor.execute("""
            INSERT INTO peer_pods (pod_name, member_name, weekly_score, streak, contribution, is_user, user_id)
            VALUES ('ROAD GUARDIANS', ?, 100, 0, 0, 1, ?)
        """, (uname, user_id))
        conn.commit()

    if points_change != 0:
        cursor.execute("""
            UPDATE peer_pods 
            SET contribution = MAX(0, contribution + ?) 
            WHERE is_user = 1 AND user_id = ?
        """, (points_change, user_id))
        
    conn.commit()
    conn.close()
    return {"status": "success", "points_change": points_change}
