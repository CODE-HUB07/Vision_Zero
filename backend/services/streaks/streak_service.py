from database.database import get_db_connection

def get_streak_summary():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT current_streak, longest_streak, last_trip_date FROM streaks WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    
    current = row['current_streak'] if row else 0
    longest = row['longest_streak'] if row else 0
    last_date = row['last_trip_date'] if row else None
    
    milestones = [
        {"days": 7, "points": 100, "unlocked": current >= 7, "progress": min(100, int(current / 7 * 100))},
        {"days": 30, "points": 500, "unlocked": current >= 30, "progress": min(100, int(current / 30 * 100))},
        {"days": 90, "points": 1500, "unlocked": current >= 90, "progress": min(100, int(current / 90 * 100))}
    ]
    
    return {
        "current_streak": current,
        "longest_streak": longest,
        "last_trip_date": last_date,
        "milestones": milestones
    }
