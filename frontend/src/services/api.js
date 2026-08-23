const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api";

async function request(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const headers = {
    "Content-Type": "application/json",
    ...options.headers,
  };
  
  const response = await fetch(url, { ...options, headers });
  if (!response.ok) {
    const errText = await response.text();
    let message = "Network response was not ok";
    try {
      const parsed = JSON.parse(errText);
      message = parsed.detail || message;
    } catch (_) {
      message = errText || message;
    }
    throw new Error(message);
  }
  return response.json();
}

export const api = {
  // Settings
  getSettings: () => request("/settings"),
  updateSettings: (settings) => request("/settings", { method: "POST", body: JSON.stringify(settings) }),
  
  // Trips
  startTrip: (tripId, mode, startTime) => request("/trips/start", {
    method: "POST",
    body: JSON.stringify({ trip_id: tripId, mode, start_time: startTime })
  }),
  sendTelemetryTick: (tickData) => request("/trips/tick", {
    method: "POST",
    body: JSON.stringify(tickData)
  }),
  endTrip: (tripId, endTime) => request("/trips/end", {
    method: "POST",
    body: JSON.stringify({ trip_id: tripId, end_time: endTime })
  }),
  listTrips: (sortBy = "Latest") => request(`/trips?sort_by=${encodeURIComponent(sortBy)}`),
  getTrip: (tripId) => request(`/trips/${tripId}`),
  deleteTrip: (tripId) => request(`/trips/${tripId}`, { method: "DELETE" }),
  getTripTelemetry: (tripId) => request(`/trips/${tripId}/telemetry`),
  getTripEvents: (tripId) => request(`/trips/${tripId}/events`),
  getTripNudges: (tripId) => request(`/trips/${tripId}/nudges`),
  
  // Gamification
  getStreaks: () => request("/streaks"),
  getRewards: () => request("/rewards"),
  redeemReward: (rewardId) => request("/rewards/redeem", {
    method: "POST",
    body: JSON.stringify({ reward_id: rewardId })
  }),
  getRedemptionHistory: () => request("/rewards/history"),
  getBadges: () => request("/badges"),
  submitSelfReport: (eventType, description, timestamp) => request("/self-report", {
    method: "POST",
    body: JSON.stringify({ event_type: eventType, description, timestamp })
  }),
  
  // Pods
  getPeerPod: () => request("/peer-pod"),
  
  // Analytics
  getAnalytics: (timeFilter = "30 Days") => request(`/analytics?time_filter=${encodeURIComponent(timeFilter)}`),
  
  // Global events feed
  getGlobalEvents: () => request("/events"),
};
