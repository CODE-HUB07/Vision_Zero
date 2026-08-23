from database.database import get_db_connection

def get_pod_details(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Ensure user has a record in peer_pods
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
        
    # Get all members: the current logged in user plus mock teammates
    cursor.execute("""
        SELECT * FROM peer_pods 
        WHERE (is_user = 1 AND user_id = ?) OR (is_user = 0 AND user_id IS NULL)
        ORDER BY weekly_score DESC
    """, (user_id,))
    members_rows = cursor.fetchall()
    
    # Calculate average pod reputation
    members = [dict(m) for m in members_rows]
    total_score = sum(m['weekly_score'] for m in members)
    pod_reputation = int(total_score / len(members)) if members else 0
    
    conn.close()
    
    # Mock Leaderboard for Pods
    pod_leaderboard = [
        {"pod_name": "SAFE CRUISERS", "weekly_reputation": 95, "rank": 1, "members_count": 5},
        {"pod_name": "ROAD GUARDIANS", "weekly_reputation": pod_reputation, "rank": 2, "members_count": len(members)},
        {"pod_name": "ECO FLYERS", "weekly_reputation": 87, "rank": 3, "members_count": 6},
        {"pod_name": "CITY SHIELD", "weekly_reputation": 82, "rank": 4, "members_count": 8}
    ]
    
    # Sort leaderboard dynamically
    pod_leaderboard.sort(key=lambda x: x["weekly_reputation"], reverse=True)
    for index, item in enumerate(pod_leaderboard):
        item["rank"] = index + 1
        
    user_pod_rank = next((p["rank"] for p in pod_leaderboard if p["pod_name"] == "ROAD GUARDIANS"), 2)
    
    feedback = "🏆 Keep it up! Your safe driving contributed points to ROAD GUARDIANS."
    if user_pod_rank == 1:
        feedback = "🏆 Excellent! Your Pod has moved to Rank #1 due to outstanding safety compliance!"
    elif user_pod_rank == 2:
        feedback = "💪 You're in Rank #2! Just a small safety score improvement will push ROAD GUARDIANS to the top!"
        
    return {
        "pod_name": "ROAD GUARDIANS",
        "reputation": pod_reputation,
        "rank": user_pod_rank,
        "members": members,
        "leaderboard": pod_leaderboard,
        "social_feedback": feedback
    }
