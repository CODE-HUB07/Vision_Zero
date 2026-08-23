from database.database import get_db_connection

def get_analytics_summary(user_id: int, time_filter="30 Days"):
    """
    Computes system-wide KPIs: Behavioural, Engagement, Social, and Outcomes.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Fetch user trips
    cursor.execute("SELECT * FROM trips WHERE end_time IS NOT NULL AND user_id = ?", (user_id,))
    trips = [dict(t) for t in cursor.fetchall()]
    
    total_trips = len(trips)
    
    # 1. Behavioural KPIs (Real User Performance)
    avg_speed_compliance = sum(t['speed_compliance_pct'] for t in trips) / total_trips if total_trips > 0 else 100.0
    avg_phone_free = sum(t['phone_free_pct'] for t in trips) / total_trips if total_trips > 0 else 100.0
    avg_safety_score = sum(t['safety_score'] for t in trips) / total_trips if total_trips > 0 else 100.0
    total_dist = sum(t['distance_km'] for t in trips) or 0.0
    total_overspeeds = sum(t['overspeed_count'] for t in trips)
    total_phone_uses = sum(t['phone_use_count'] for t in trips)
    
    overspeeds_per_1000km = (total_overspeeds / (total_dist / 1000.0)) if total_dist > 0 else 0.0
    phone_uses_per_trip = (total_phone_uses / total_trips) if total_trips > 0 else 0.0
    
    # 2. Engagement KPIs
    cursor.execute("SELECT COUNT(*) FROM user_rewards WHERE user_id = ?", (user_id,))
    redemptions_count = cursor.fetchone()[0]
    
    # Mocking system-wide engagement (offline requirement)
    engagement = {
        "daily_active_users": 154,
        "daily_active_pods": 12,
        "streak_retention_7d": "84%",
        "streak_retention_30d": "62%",
        "reward_redemptions": redemptions_count
    }
    
    # 3. Social KPIs
    # Standings changes and peer feedback engagement
    social = {
        "peer_reports_submitted": 3,
        "badge_shares": 8,
        "community_nominations": 2,
        "pod_participation_rate": "92%",
        "pod_ranking_changes": "+1 place this week"
    }
    
    # 4. Outcomes (Before vs After) - Labeled Demonstration Data
    # Before refers to historical baseline of the driver community/individual before using the engine.
    # After refers to user's actual telemetry achievements under nudges.
    before_data = {
        "speed_compliance_pct": 72.0,
        "phone_free_pct": 78.0,
        "avg_safety_score": 74.0,
        "overspeed_events_per_100km": 18.5,
        "phone_use_events_per_100km": 12.2
    }
    
    after_data = {
        "speed_compliance_pct": round(avg_speed_compliance, 1),
        "phone_free_pct": round(avg_phone_free, 1),
        "avg_safety_score": round(avg_safety_score, 1),
        "overspeed_events_per_100km": round((total_overspeeds / (total_dist / 100.0)) if total_dist > 0 else 0.5, 1),
        "phone_use_events_per_100km": round((total_phone_uses / (total_dist / 100.0)) if total_dist > 0 else 0.4, 1)
    }
    
    # 5. Speed Compliance over time (for charts)
    compliance_over_time = []
    for i, t in enumerate(trips):
        compliance_over_time.append({
            "trip_num": i + 1,
            "date": t["start_time"][:10] if t["start_time"] else f"Trip {i+1}",
            "compliance": t["speed_compliance_pct"],
            "phone_free": t["phone_free_pct"],
            "score": t["safety_score"]
        })
        
    # If no trips yet, yield dummy charts
    if not compliance_over_time:
        compliance_over_time = [
            {"trip_num": 1, "date": "Run 1", "compliance": 95, "phone_free": 98, "score": 98},
            {"trip_num": 2, "date": "Run 2", "compliance": 98, "phone_free": 100, "score": 100}
        ]
        
    conn.close()
    
    return {
        "behavioural": {
            "avg_speed_compliance_pct": round(avg_speed_compliance, 1),
            "avg_phone_free_pct": round(avg_phone_free, 1),
            "avg_safety_score": round(avg_safety_score, 1),
            "total_distance_km": round(total_dist, 2),
            "overspeeds_per_1000km": round(overspeeds_per_1000km, 1),
            "phone_uses_per_trip": round(phone_uses_per_trip, 1),
            "total_overspeeds": total_overspeeds,
            "total_phone_uses": total_phone_uses,
            "total_trips": total_trips
        },
        "engagement": engagement,
        "social": social,
        "demonstration_before_after": {
            "before": before_data,
            "after": after_data,
            "label": "DEMONSTRATION DATA - Historical Driver Community vs Current User Compliance"
        },
        "compliance_over_time": compliance_over_time
    }
