# SafeGuard Compliance Engine

An offline-first telemetry processing and driver compliance dashboard. Designed to ingest raw trip telematics (vehicle speed, GPS, and active phone distraction indicators) and convert them into auditable risk profiles, safe-driving streaks, and collaborative pod standings using transition-based heuristics.

---

## 📖 Product Philosophy

Driver monitoring systems are frequently perceived as purely punitive. SafeGuard takes the opposite approach: **making safe driving socially desirable and rewarding**. The platform operates on a feedback loop of real-time coaching nudges, gamified credit accumulations, and regional peer pods to encourage long-term behavioral compliance.

```
Driver Session ──> Telemetry Stream ──> Transition Risk Heuristics ──> Active HUD Coaching Nudge
                                                                             │
  ┌──────────────────────────────────────────────────────────────────────────┘
  ▼
Trip Completion Assessment ──> Safety Score Calibration ──> Pod Contribution & Standings
```

---

## 🏗️ Architecture & Component Layout

SafeGuard is structured around a decoupled frontend-backend architecture:

- **Frontend (Vite + React + Tailwind CSS)**: Optimized for performance and responsiveness. Featuring the **Active Safety HUD** (an instrumentation panel designed for clear scanning while driving), tabular-figure typography to eliminate jitter during active updates, and a dynamically-scaling Canvas visualizer rendering telemetry trajectories at 60fps.
- **Backend (FastAPI + SQLite)**: An offline-first ingestion pipeline. Compliance calculations are processed in Python to guarantee logic parity across simulator runs, live recordings, and dataset replays.

### Ingestion Modes

1. **Active Safety HUD (Simulator)**: A live streaming environment that simulates vehicle drift and alerts.
2. **Trip Logging Console (Manual Recording)**: Allows a driver to override values to log honest deviations, helping to simulate test profiles.
3. **Replay Console (Pre-Recorded playback)**: Plays back 5 standard telemetry scenarios (Speeding, Phone distraction, Improving Behavior, High Risk, and Safe Driver) to verify engine predictability under audit conditions.

---

## ⚙️ Core Engines

### 1. Transition-Based Risk Hysteresis
To prevent alert fatigue and score depletion, the system queries SQLite for the previous telemetry frame state. Alerts and scoring penalties only trigger when crossing boundaries:
- **`SAFE` -> `WARNING`**: Minor speed threshold exceeded (+5 km/h tolerance).
- **`WARNING` -> `HIGH_RISK`**: Severe speed threshold exceeded (+15 km/h tolerance) or phone usage detected.
- **`HIGH_RISK` / `WARNING` -> `SAFE`**: Recovery logged, firing a coaching resolution nudge.

### 2. Safety Scoring Model
Trips begin with a clean index of `100/100`. Deductions are computed instantly per transition event:
- Minor speed warning: `-5` index points.
- Severe speeding warning: `-10` index points.
- Phone distraction: `-10` index points.

Scoring thresholds and deduction weights are fully configurable within the **Threshold Calibration** panel.

---

## 🚀 Installation & Local Development

Ensure you have Python 3.10+ and Node.js 18+ installed.

### 1. Backend Service Configuration
```bash
# Navigate to the workspace root
pip install -r requirements.txt

# Start the FastAPI daemon (defaults to http://127.0.0.1:8000)
python backend/main.py
```
*The daemon will automatically provision and seed the SQLite database file (`backend/database/traffic_compliance.db`) if it doesn't already exist.*

### 2. Frontend Client Configuration
```bash
# Navigate to client assets folder
cd frontend
npm install

# Start the Vite local server (http://localhost:5173/)
npm run dev
```

---

## 📋 Audit Verification Logs

All verification logs pass standard telemetry compliance audits:
1. **Pipeline Continuity**: Real-time mode tracks controls and registers speed corrections.
2. **Deterministic Output**: Replaying identical custom recordings outputs matching safety scores and event timelines.
3. **Edge-Case Resilience**: The user interface has built-in toggles to simulate empty audit databases, truncated long names, and partial regional pods, preventing layout regression under pressure.
