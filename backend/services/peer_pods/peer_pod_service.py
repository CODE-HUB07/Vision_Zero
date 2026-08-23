from database.database import get_db_connection

def get_pod_details():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all members of ROAD GUARDIANS
    cursor.execute("SELECT * FROM peer_pods WHERE pod_name = 'ROAD GUARDIANS' ORDER BY weekly_score DESC")
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
