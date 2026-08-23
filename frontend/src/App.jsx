import React, { useState, useEffect, useRef } from "react";
import {
  Shield,
  Radio,
  History,
  Users,
  Award,
  AlertTriangle,
  Play,
  Pause,
  Check,
  X,
  Trash2,
  ChevronRight,
  UserCheck,
  Lock,
  Unlock,
  Menu,
  ChevronLeft,
  Mail,
  RefreshCw,
  LogOut
} from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid
} from "recharts";
import emailjs from "@emailjs/browser";
import { api } from "./services/api";
import VisualizerCanvas from "./components/VisualizerCanvas";

const EMAILJS_SERVICE_ID = (import.meta.env.VITE_EMAILJS_SERVICE_ID || "service_qemilcy").trim().replace(/['"]/g, "");
const EMAILJS_TEMPLATE_ID = (import.meta.env.VITE_EMAILJS_TEMPLATE_ID || "template_n4q1n9a").trim().replace(/['"]/g, "");
const EMAILJS_PUBLIC_KEY = (import.meta.env.VITE_EMAILJS_PUBLIC_KEY || "rAg8ZjmaFTEu0M1lV").trim().replace(/['"]/g, "");

const isEmailJSDemoMode = 
  !EMAILJS_SERVICE_ID || 
  EMAILJS_PUBLIC_KEY === "user_safeguard_pk" ||
  !EMAILJS_PUBLIC_KEY;

export default function App() {
  const [activeTab, setActiveTab] = useState("Dashboard");
  const [toast, setToast] = useState(null);

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  const showToast = (message, type = "success") => {
    setToast({ message, type });
  };
  
  // Auth state
  const [token, setToken] = useState(localStorage.getItem("safeguard_token"));
  const [user, setUser] = useState(null);
  const [isAuthLoading, setIsAuthLoading] = useState(true);
  
  // Auth forms state
  const [authMode, setAuthMode] = useState("login"); // "login" or "register"
  const [authName, setAuthName] = useState("");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authError, setAuthError] = useState("");
  const [authLoading, setAuthLoading] = useState(false);

  // Settings & state
  const [settings, setSettings] = useState({
    warning_threshold: 5,
    critical_threshold: 15,
    weight_minor_overspeed: 5,
    weight_severe_overspeed: 10,
    weight_phone_use: 10,
    privacy_telemetry_on: true,
    privacy_location_minimal: true,
    privacy_data_retention_days: 30,
    privacy_sharing_on: true,
    parent_email: "",
    guardian_enabled: false
  });
  
  const [dashboardStats, setDashboardStats] = useState(null);
  const [globalEvents, setGlobalEvents] = useState([]);
  const [streaks, setStreaks] = useState({ current_streak: 0, longest_streak: 0, milestones: [] });
  const [rewards, setRewards] = useState({ points: { balance: 0, total_earned: 0 }, catalog: [] });
  const [redemptions, setRedemptions] = useState([]);
  const [peerPod, setPeerPod] = useState({ pod_name: "ROAD GUARDIANS", reputation: 90, rank: 2, members: [], leaderboard: [] });
  const [completedTrips, setCompletedTrips] = useState([]);
  const [notificationsHistory, setNotificationsHistory] = useState([]);
  
  // Profile Forms state
  const [profileName, setProfileName] = useState("");
  const [profilePassword, setProfilePassword] = useState("");
  const [profileOldPassword, setProfileOldPassword] = useState("");

  // Trip history configurations
  const [historySort, setHistorySort] = useState("Latest");
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [selectedReportTrip, setSelectedReportTrip] = useState(null);
  const [selectedTripEvents, setSelectedTripEvents] = useState([]);
  
  // Edge-case simulators
  const [simulateEmptyHistory, setSimulateEmptyHistory] = useState(false);
  const [simulateSmallPod, setSimulateSmallPod] = useState(false);
  
  // HUD Ingestion Session states
  const [activeTrip, setActiveTrip] = useState(null); 
  const [isTripRunning, setIsTripRunning] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1); // 1x, 2x, 5x, 10x
  
  // Unified HUD Live Ingestion controller values
  const [autopilotEnabled, setAutopilotEnabled] = useState(false);
  const [manualSpeed, setManualSpeed] = useState(30);
  const [manualLimit, setManualLimit] = useState(40);
  const [manualPhone, setManualPhone] = useState(false);
  const [activeNudge, setActiveNudge] = useState(null);
  
  // Ref handles to avoid stale state closures inside intervals
  const activeTripRef = useRef(null);
  const recordingSpeedRef = useRef(30);
  const recordingPhoneRef = useRef(false);
  const recordingLimitRef = useRef(40);
  const simulatorTimerRef = useRef(null);
  const emailSentRef = useRef({ OVERSPEED: false, PHONE_USE: false });
  
  // Sync active trip reference for the timer thread
  useEffect(() => {
    activeTripRef.current = activeTrip;
  }, [activeTrip]);

  const deviceLocationRef = useRef(null);

  useEffect(() => {
    if (!navigator.geolocation) return;
    const watchId = navigator.geolocation.watchPosition(
      (position) => {
        deviceLocationRef.current = {
          latitude: position.coords.latitude,
          longitude: position.coords.longitude
        };
      },
      (error) => {
        console.warn("Geolocation watch failed:", error);
      },
      {
        enableHighAccuracy: true,
        timeout: 10000,
        maximumAge: 0
      }
    );
    return () => navigator.geolocation.clearWatch(watchId);
  }, []);

  // Handle dynamic changes in playback speed factor during active runs
  useEffect(() => {
    if (!isTripRunning || !activeTrip) return;
    if (simulatorTimerRef.current) {
      // Re-trigger simulator timer with the new speed factor
      startHUDPlaybackTimer(playbackSpeed);
    }
  }, [playbackSpeed, isTripRunning]);

  const audioCtxRef = useRef(null);
  const oscillatorRef = useRef(null);
  const vibrationIntervalRef = useRef(null);

  const startAlertSound = () => {
    if (oscillatorRef.current) {
      updateAlertParameters();
      return;
    }
    
    try {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) return;
      
      const ctx = new AudioContextClass();
      audioCtxRef.current = ctx;
      
      const osc = ctx.createOscillator();
      const gainNode = ctx.createGain();
      
      oscillatorRef.current = osc;
      osc.type = "sawtooth"; // grating sawtooth buzzer
      
      const isHighRisk = activeTripRef.current?.riskLevel === "HIGH_RISK";
      const freq = isHighRisk ? 1100 : 880; 
      
      osc.frequency.setValueAtTime(freq, ctx.currentTime);
      gainNode.gain.setValueAtTime(isHighRisk ? 0.08 : 0.04, ctx.currentTime); 
      
      osc.connect(gainNode);
      gainNode.connect(ctx.destination);
      osc.start();
      
      // Continuous haptic vibration pulses
      vibrationIntervalRef.current = setInterval(() => {
        if (navigator.vibrate) {
          const isHigh = activeTripRef.current?.riskLevel === "HIGH_RISK";
          navigator.vibrate(isHigh ? [150, 100, 150] : 200);
        }
      }, 600);
      
    } catch (e) {
      console.error("Sound generation error:", e);
    }
  };

  const updateAlertParameters = () => {
    const osc = oscillatorRef.current;
    const ctx = audioCtxRef.current;
    if (!osc || !ctx) return;
    
    const isHighRisk = activeTripRef.current?.riskLevel === "HIGH_RISK";
    const freq = isHighRisk ? 1100 : 880;
    
    osc.frequency.setValueAtTime(freq, ctx.currentTime);
  };

  const stopAlertSound = () => {
    if (oscillatorRef.current) {
      try {
        oscillatorRef.current.stop();
      } catch (_) {}
      oscillatorRef.current = null;
    }
    if (vibrationIntervalRef.current) {
      clearInterval(vibrationIntervalRef.current);
      vibrationIntervalRef.current = null;
    }
    if (audioCtxRef.current) {
      try {
        audioCtxRef.current.close();
      } catch (_) {}
      audioCtxRef.current = null;
    }
  };

  // Warning & risk phase audio alerts controller
  useEffect(() => {
    if (isTripRunning && activeTrip && (activeTrip.riskLevel === "WARNING" || activeTrip.riskLevel === "HIGH_RISK")) {
      startAlertSound();
    } else {
      stopAlertSound();
    }
    
    return () => {
      stopAlertSound();
    };
  }, [isTripRunning, activeTrip?.riskLevel]);

  // Auth verify effect
  useEffect(() => {
    if (token) {
      api.getMe()
        .then(res => {
          setUser(res);
          setProfileName(res.name);
          setIsAuthLoading(false);
        })
        .catch(err => {
          console.error("Session verification failed:", err);
          handleLogout();
          setIsAuthLoading(false);
        });
    } else {
      setIsAuthLoading(false);
    }
  }, [token]);

  // Load user details when user state is initialized
  useEffect(() => {
    if (user) {
      loadSettings();
      loadDashboardData();
      loadTripHistory();
      loadNotificationsHistory();
    }
  }, [user]);

  const loadSettings = async () => {
    try {
      const data = await api.getSettings();
      setSettings(prev => ({
        ...prev,
        ...data,
        guardian_enabled: user ? !!user.guardian_enabled : false
      }));
    } catch (e) {
      console.error("Error loading settings:", e);
    }
  };

  const loadDashboardData = async () => {
    try {
      const analytics = await api.getAnalytics();
      setDashboardStats(analytics);
      
      const feed = await api.getGlobalEvents();
      setGlobalEvents(feed);
      
      const st = await api.getStreaks();
      setStreaks(st);
      
      const rw = await api.getRewards();
      setRewards(rw);
      
      const rh = await api.getRedemptionHistory();
      setRedemptions(rh);
      
      const pod = await api.getPeerPod();
      setPeerPod(pod);
    } catch (e) {
      console.error("Error loading dashboard data:", e);
    }
  };

  const loadTripHistory = async (sortVal = historySort) => {
    try {
      const list = await api.listTrips(sortVal);
      setCompletedTrips(list);
    } catch (e) {
      console.error("Error loading trip history:", e);
    }
  };

  const loadNotificationsHistory = async () => {
    try {
      const list = await api.getNotificationsHistory();
      setNotificationsHistory(list);
    } catch (e) {
      console.error("Error loading notifications history:", e);
    }
  };

  const handleRetryNotifications = async () => {
    try {
      const res = await api.retryNotifications();
      alert(`Retry transmission complete. Attempts: ${res.retried_count}, Succeeded: ${res.success_count}`);
      loadNotificationsHistory();
    } catch (e) {
      alert("Failed to retry queued notifications: " + e.message);
    }
  };

  const deleteTrip = async (tripId) => {
    if (!confirm("Are you sure you want to delete this trip record?")) return;
    try {
      await api.deleteTrip(tripId);
      if (selectedReportTrip?.id === tripId) {
        setSelectedReportTrip(null);
      }
      loadDashboardData();
      loadTripHistory();
    } catch (e) {
      alert("Failed to delete trip: " + e.message);
    }
  };

  const handleAuthSubmit = async (e) => {
    e.preventDefault();
    setAuthError("");
    setAuthLoading(true);
    try {
      if (authMode === "login") {
        const res = await api.login(authEmail, authPassword);
        localStorage.setItem("safeguard_token", res.token);
        setToken(res.token);
        setUser(res.user);
      } else {
        const res = await api.register(authName, authEmail, authPassword);
        localStorage.setItem("safeguard_token", res.token);
        setToken(res.token);
        setUser(res.user);
      }
    } catch (err) {
      setAuthError(err.message || "Authentication failed.");
    } finally {
      setAuthLoading(false);
    }
  };

  const handleLogout = () => {
    try {
      if (api.logout) {
        api.logout().catch(() => {});
      }
    } catch (_) {}
    
    // Clear active simulation timer and states on logout
    if (simulatorTimerRef.current) {
      clearInterval(simulatorTimerRef.current);
      simulatorTimerRef.current = null;
    }
    setIsTripRunning(false);
    setActiveTrip(null);
    stopAlertSound();
    
    localStorage.removeItem("safeguard_token");
    setToken(null);
    setUser(null);
  };

  const handleProfileUpdate = async (e) => {
    e.preventDefault();
    try {
      // 1. Update user credentials and guardian flags
      await api.updateProfile({
        name: profileName,
        password: profilePassword || null,
        old_password: profileOldPassword || null,
        guardian_email: settings.parent_email,
        guardian_enabled: settings.guardian_enabled
      });
      
      // 2. Update config parameters
      await api.updateSettings(settings);
      
      showToast("Account information and threshold settings saved.", "success");
      
      // Refresh local user state
      const updatedUser = await api.getMe();
      setUser(updatedUser);
      setProfilePassword("");
      setProfileOldPassword("");
      
      loadSettings();
      loadNotificationsHistory();
    } catch (err) {
      showToast("Failed to update profile settings: " + err.message, "error");
    }
  };

  // --- Real-time Parental Alerts via EmailJS ---
  const sendParentEmailViaEmailJS = (eventType, speed, limit, tripId, latitude = null, longitude = null) => {
    console.log(`[EmailJS] Initiating parent email alert for event: ${eventType}`);
    
    // Default EmailJS credentials with safe fallbacks
    const serviceId = EMAILJS_SERVICE_ID;
    const templateId = EMAILJS_TEMPLATE_ID;
    const publicKey = EMAILJS_PUBLIC_KEY;

    const lat = latitude !== null ? Number(latitude).toFixed(4) : "12.9716";
    const lon = longitude !== null ? Number(longitude).toFixed(4) : "77.5946";
    const mapsUrl = `https://www.google.com/maps/search/?api=1&query=${lat},${lon}`;

    const templateParams = {
      driver_name: user ? user.name : "Driver",
      parent_email: settings.parent_email,
      event_type: eventType,
      speed: speed ? Math.round(speed) : "N/A",
      speed_limit: limit ? Math.round(limit) : "N/A",
      timestamp: new Date().toLocaleString(),
      risk_level: eventType === "OVERSPEED" ? "WARNING" : "HIGH_RISK",
      time: new Date().toLocaleTimeString(),
      phone_use: eventType === "PHONE_USE" ? "Yes (Exception Flagged)" : "No (Secure)",
      location: `${lat}, ${lon}`,
      google_maps_link: mapsUrl
    };

    emailjs.send(serviceId, templateId, templateParams, publicKey)
      .then((res) => {
        console.log("EmailJS Sent Successful:", res.status, res.text);
        showToast("Guardian alert email sent successfully to " + settings.parent_email, "success");
        // Update DB status to SENT
        api.updateNotificationStatus(tripId, eventType, "SENT")
          .then(() => loadNotificationsHistory())
          .catch(e => console.error("Failed to update DB notification status:", e));
      })
      .catch((err) => {
        console.error("EmailJS Sent Failed, queuing message:", err);
        showToast("EmailJS transmission failed (queued locally): " + (err.text || err.message || err), "error");
        // Ensure status stays QUEUED so manual retries are enabled
        api.updateNotificationStatus(tripId, eventType, "QUEUED")
          .then(() => loadNotificationsHistory())
          .catch(e => console.error("Failed to update DB notification status:", e));
      });
  };

  // --- Unified HUD Ingestion Engine ---
  const startIngestionSession = async () => {
    if (isTripRunning) return;
    
    const mode = autopilotEnabled ? "REAL_TIME" : "RECORDED";
    const tripId = `trip_${Date.now()}`;
    const startTime = new Date().toLocaleTimeString();
    
    try {
      await api.startTrip(tripId, mode, startTime);
      
      const initialSession = {
        id: tripId,
        mode,
        speed: autopilotEnabled ? 30 : manualSpeed,
        speedLimit: autopilotEnabled ? 40 : manualLimit,
        phoneUse: autopilotEnabled ? false : manualPhone,
        riskLevel: "SAFE",
        score: 100,
        duration: 0,
        distance: 0,
        events: [],
        ticks: []
      };
      
      // Seed refs
      recordingSpeedRef.current = autopilotEnabled ? 30 : manualSpeed;
      recordingPhoneRef.current = autopilotEnabled ? false : manualPhone;
      recordingLimitRef.current = autopilotEnabled ? 40 : manualLimit;
      emailSentRef.current = { OVERSPEED: false, PHONE_USE: false };
      
      setActiveTrip(initialSession);
      setIsTripRunning(true);
      setActiveNudge(null);
      
      startHUDPlaybackTimer(playbackSpeed, tripId);
    } catch (e) {
      alert("Failed to start ingestion session: " + e.message);
    }
  };

  const startHUDPlaybackTimer = (speedFactor, customTripId = null) => {
    if (simulatorTimerRef.current) clearInterval(simulatorTimerRef.current);
    
    const tickRate = 1000 / speedFactor;
    
    simulatorTimerRef.current = setInterval(async () => {
      const session = activeTripRef.current;
      const tId = customTripId || session?.id;
      if (!tId) return;
      
      const duration = session ? session.duration + 1 : 1;
      
      let nextSpeed = recordingSpeedRef.current;
      let nextPhone = recordingPhoneRef.current;
      const nextLimit = recordingLimitRef.current;
      
      if (autopilotEnabled) {
        // Drift vehicle parameters automatically
        const drift = (Math.random() - 0.45) * 6;
        nextSpeed = Math.max(0, Math.min(130, nextSpeed + drift));
        recordingSpeedRef.current = nextSpeed;
        setManualSpeed(Math.round(nextSpeed));
        
        // Random distraction triggers (5% chance)
        if (!nextPhone && Math.random() < 0.05) {
          nextPhone = true;
          recordingPhoneRef.current = true;
          setManualPhone(true);
        } else if (nextPhone && Math.random() < 0.3) {
          nextPhone = false;
          recordingPhoneRef.current = false;
          setManualPhone(false);
        }
      }
      
      try {
        const timestamp = new Date().toLocaleTimeString();
        let lat = 12.9716 + (duration * 0.0001);
        let lon = 77.5946 + (duration * 0.00015);
        if (deviceLocationRef.current) {
          lat = deviceLocationRef.current.latitude;
          lon = deviceLocationRef.current.longitude;
        }
        
        const response = await api.sendTelemetryTick({
          trip_id: tId,
          speed: nextSpeed,
          speed_limit: nextLimit,
          phone_use: nextPhone,
          timestamp,
          latitude: lat,
          longitude: lon,
          source: autopilotEnabled ? "simulator" : "manual"
        });
        
        const addedDist = (nextSpeed / 3600.0);
        const distance = session ? session.distance + addedDist : addedDist;
        
        // Resolve or trigger warning nudges
        if (response.nudges && response.nudges.length > 0) {
          setActiveNudge(response.nudges[0]);
        } else if (response.risk_level === "SAFE") {
          setActiveNudge(null);
        }

        // Trigger real-time Parental alerts via EmailJS library
        if (settings.guardian_enabled && settings.parent_email && settings.parent_email.includes("@")) {
          if (response.events && response.events.length > 0) {
            response.events.forEach(ev => {
              if (ev.event_type === "OVERSPEED" && !emailSentRef.current.OVERSPEED) {
                emailSentRef.current.OVERSPEED = true;
                sendParentEmailViaEmailJS("OVERSPEED", ev.speed, ev.speed_limit, tId, lat, lon);
              } else if (ev.event_type === "PHONE_USE" && !emailSentRef.current.PHONE_USE) {
                emailSentRef.current.PHONE_USE = true;
                sendParentEmailViaEmailJS("PHONE_USE", ev.speed, ev.speed_limit, tId, lat, lon);
              }
            });
          }
        }
        
        setActiveTrip(prev => {
          if (!prev) return null;
          const updatedEvents = [...prev.events];
          if (response.events && response.events.length > 0) {
            updatedEvents.push(...response.events);
          }
          const updatedTicks = [...prev.ticks, {
            speed: nextSpeed,
            speed_limit: nextLimit,
            phone_use: nextPhone,
            risk_level: response.risk_level
          }];
          
          return {
            ...prev,
            speed: nextSpeed,
            speedLimit: nextLimit,
            phoneUse: nextPhone,
            riskLevel: response.risk_level,
            score: response.safety_score,
            duration,
            distance,
            events: updatedEvents,
            ticks: updatedTicks
          };
        });
      } catch (err) {
        console.error("Tick error:", err);
      }
    }, tickRate);
  };

  const adjustHUDSpeed = (amount) => {
    const target = Math.max(0, Math.min(130, manualSpeed + amount));
    setManualSpeed(target);
    recordingSpeedRef.current = target;
  };

  const toggleHUDPhone = (phoneState) => {
    setManualPhone(phoneState);
    recordingPhoneRef.current = phoneState;
  };

  const changeHUDLimit = (limitVal) => {
    setManualLimit(limitVal);
    recordingLimitRef.current = limitVal;
  };

  const stopIngestionSession = async () => {
    const session = activeTripRef.current;
    if (!session) return;
    
    if (simulatorTimerRef.current) clearInterval(simulatorTimerRef.current);
    setIsTripRunning(false);
    
    try {
      const endTime = new Date().toLocaleTimeString();
      const result = await api.endTrip(session.id, endTime);
      
      setActiveNudge(null);
      loadDashboardData();
      loadTripHistory();
      loadNotificationsHistory();
      
      // Update activeTrip with completion stats to render summary card
      setActiveTrip(prev => ({
        ...prev,
        finalSummary: result.trip,
        streakResult: result.streak
      }));
    } catch (e) {
      alert("Failed to stop ingestion session: " + e.message);
    }
  };

  // --- Rewards Redemption Controller ---
  const redeemReward = async (rewardId) => {
    try {
      const response = await api.redeemReward(rewardId);
      alert(`Successfully redeemed: ${response.redemption?.name || "Reward"}`);
      loadDashboardData();
    } catch (e) {
      alert("Failed to redeem reward: " + e.message);
    }
  };

  // --- Derived Statistics ---
  const totalScoreAverage = completedTrips.length > 0
    ? (completedTrips.reduce((acc, t) => acc + t.safety_score, 0) / completedTrips.length).toFixed(1)
    : "100.0";

  const totalSpeedCompliance = completedTrips.length > 0
    ? (completedTrips.reduce((acc, t) => acc + t.speed_compliance_pct, 0) / completedTrips.length).toFixed(0)
    : "100";

  const totalPhoneFreeCompliance = completedTrips.length > 0
    ? (completedTrips.reduce((acc, t) => acc + t.phone_free_pct, 0) / completedTrips.length).toFixed(0)
    : "100";

  const streakVal = streaks.current_streak || 0;
  const nextMilestoneCount = 10;
  const streakProgressPct = Math.min(100, (streakVal / nextMilestoneCount) * 100);

  // Filter lists based on mock switch states
  const renderTripsList = simulateEmptyHistory ? [] : completedTrips;
  const podMembers = simulateSmallPod ? peerPod.members.slice(0, 3) : peerPod.members;

  const activeTabTitle = activeTab === "Dashboard" ? "Driver Hub"
    : activeTab === "HUD" ? "Active Safety HUD"
    : activeTab === "History" ? "Historical Audits"
    : activeTab === "Leaderboard" ? "Leaderboard standings"
    : activeTab === "Rewards" ? "Rewards balance & redemptions"
    : "Profile & safety settings";

  // Login Check
  if (isAuthLoading) {
    return (
      <div className="min-h-screen bg-safety-dark flex flex-col items-center justify-center">
        <div className="w-10 h-10 border-4 border-safety-primary border-t-transparent rounded-full animate-spin mb-4" />
        <span className="text-xs font-bold text-safety-textSecondary uppercase tracking-widest">Verifying Compliance Session...</span>
      </div>
    );
  }

  if (!token || !user) {
    return (
      <div className="min-h-screen bg-safety-dark flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-md w-full space-y-8 bg-white border border-safety-border p-8 rounded-lg shadow-sm">
          <div className="flex flex-col items-center">
            <div className="w-12 h-12 rounded-full bg-teal-50 flex items-center justify-center mb-3">
              <Shield className="w-6 h-6 text-safety-primary" />
            </div>
            <h2 className="text-2xl font-extrabold text-safety-textPrimary uppercase tracking-wider font-display text-center">
              SafeGuard Compliance
            </h2>
            <p className="mt-2 text-xs text-safety-textSecondary tracking-wider uppercase">
              {authMode === "login" ? "Sign in to your driver account" : "Create a new driver profile"}
            </p>
          </div>

          <form className="mt-8 space-y-4" onSubmit={handleAuthSubmit}>
            {authError && (
              <div className="p-3 bg-red-50 border border-red-200 text-safety-critical text-xs rounded font-medium">
                {authError}
              </div>
            )}
            
            {authMode === "register" && (
              <div>
                <label className="block text-[10px] font-bold text-safety-textSecondary uppercase tracking-widest mb-1.5">
                  Driver Name
                </label>
                <input
                  type="text"
                  required
                  value={authName}
                  onChange={(e) => setAuthName(e.target.value)}
                  placeholder="e.g. John Doe"
                  className="w-full bg-slate-50 border border-safety-border text-xs rounded p-2.5 text-slate-900 focus:outline-none focus:border-safety-primary focus:bg-white transition-colors"
                />
              </div>
            )}

            <div>
              <label className="block text-[10px] font-bold text-safety-textSecondary uppercase tracking-widest mb-1.5">
                Email Address
              </label>
              <input
                type="email"
                required
                value={authEmail}
                onChange={(e) => setAuthEmail(e.target.value)}
                placeholder="driver@fleet.com"
                className="w-full bg-slate-50 border border-safety-border text-xs rounded p-2.5 text-slate-900 focus:outline-none focus:border-safety-primary focus:bg-white transition-colors"
              />
            </div>

            <div>
              <label className="block text-[10px] font-bold text-safety-textSecondary uppercase tracking-widest mb-1.5">
                Password
              </label>
              <input
                type="password"
                required
                value={authPassword}
                onChange={(e) => setAuthPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-slate-50 border border-safety-border text-xs rounded p-2.5 text-slate-900 focus:outline-none focus:border-safety-primary focus:bg-white transition-colors"
              />
            </div>

            <button
              type="submit"
              disabled={authLoading}
              className="w-full py-3 bg-safety-primary text-white hover:bg-teal-700 rounded text-xs font-bold uppercase tracking-widest transition-colors flex items-center justify-center gap-2"
            >
              {authLoading ? (
                <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <span>{authMode === "login" ? "Sign In" : "Register Profile"}</span>
              )}
            </button>
          </form>

          <div className="text-center pt-4 border-t border-safety-border">
            <button
              onClick={() => {
                setAuthMode(authMode === "login" ? "register" : "login");
                setAuthError("");
              }}
              className="text-xs font-semibold text-safety-primary hover:underline uppercase tracking-wider"
            >
              {authMode === "login" ? "Create an account" : "Back to sign in"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-safety-dark text-safety-textPrimary font-sans overflow-hidden">
      
      {/* Sidebar Navigation - Desktop */}
      <aside className="hidden md:flex flex-col w-64 bg-white border-r border-safety-border shrink-0">
        <div className="h-16 flex items-center px-6 border-b border-safety-border">
          <div className="flex items-center gap-2">
            <Shield className="w-5 h-5 text-safety-primary" />
            <span className="font-extrabold text-sm tracking-wider text-safety-primary uppercase">SAFEGUARD</span>
          </div>
        </div>
        
        <nav className="flex-1 px-4 py-6 space-y-1">
          {[
            { id: "Dashboard", icon: Shield, label: "Driver Hub" },
            { id: "HUD", icon: Radio, label: "Active Safety HUD" },
            { id: "History", icon: History, label: "Historical Audits" },
            { id: "Leaderboard", icon: Users, label: "Leaderboard" },
            { id: "Rewards", icon: Award, label: "Rewards" },
            { id: "Profile", icon: UserCheck, label: "Profile" }
          ].map(item => {
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  setActiveTab(item.id);
                  setSelectedReportTrip(null);
                }}
                className={`w-full flex items-center gap-3 px-4 py-2.5 rounded text-xs font-semibold uppercase tracking-wider transition-colors ${
                  isActive
                    ? "bg-teal-50/60 text-safety-primary"
                    : "text-safety-textSecondary hover:bg-slate-50 hover:text-safety-textPrimary"
                }`}
              >
                <item.icon className="w-4 h-4" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="p-4 border-t border-safety-border space-y-3">
          <div className="text-xs font-semibold text-safety-textPrimary truncate px-2">
            Hi, {user.name}
          </div>
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded text-[10px] font-bold text-safety-textSecondary hover:bg-red-50 hover:text-safety-critical transition-colors uppercase tracking-wider"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* Mobile Drawer */}
      {isMobileMenuOpen && (
        <div className="fixed inset-0 z-50 flex md:hidden">
          <div className="fixed inset-0 bg-black/20" onClick={() => setIsMobileMenuOpen(false)} />
          <div className="relative flex flex-col w-64 max-w-xs bg-white h-full border-r border-safety-border p-4 space-y-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Shield className="w-5 h-5 text-safety-primary" />
                <span className="font-extrabold text-xs tracking-wider text-safety-primary uppercase">SAFEGUARD</span>
              </div>
              <button onClick={() => setIsMobileMenuOpen(false)}>
                <X className="w-5 h-5 text-safety-textSecondary" />
              </button>
            </div>
            
            <nav className="space-y-1">
              {[
                { id: "Dashboard", icon: Shield, label: "Driver Hub" },
                { id: "HUD", icon: Radio, label: "Active Safety HUD" },
                { id: "History", icon: History, label: "Historical Audits" },
                { id: "Leaderboard", icon: Users, label: "Leaderboard" },
                { id: "Rewards", icon: Award, label: "Rewards" },
                { id: "Profile", icon: UserCheck, label: "Profile" }
              ].map(item => {
                const isActive = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => {
                      setActiveTab(item.id);
                      setSelectedReportTrip(null);
                      setIsMobileMenuOpen(false);
                    }}
                    className={`w-full flex items-center gap-3 px-4 py-2.5 rounded text-xs font-semibold uppercase tracking-wider transition-colors ${
                      isActive
                        ? "bg-teal-50/60 text-safety-primary"
                        : "text-safety-textSecondary hover:bg-slate-50"
                    }`}
                  >
                    <item.icon className="w-4 h-4" />
                    <span>{item.label}</span>
                  </button>
                );
              })}
            </nav>
            
            <div className="pt-4 border-t border-safety-border space-y-2">
              <div className="text-[10px] text-safety-textPrimary font-semibold truncate">
                Logged in as {user.name}
              </div>
              <button
                onClick={() => {
                  setIsMobileMenuOpen(false);
                  handleLogout();
                }}
                className="w-full flex items-center gap-2 py-1.5 rounded text-[10px] font-bold text-safety-textSecondary hover:text-safety-critical transition-colors uppercase tracking-wider"
              >
                <LogOut className="w-3.5 h-3.5" />
                <span>Sign Out</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        
        {/* Header bar */}
        <header className="h-16 bg-white border-b border-safety-border flex items-center justify-between px-6 shrink-0">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setIsMobileMenuOpen(true)}
              className="md:hidden p-1 text-safety-textSecondary hover:text-safety-textPrimary"
            >
              <Menu className="w-5 h-5" />
            </button>
            <h2 className="text-xs font-bold text-safety-textPrimary uppercase tracking-widest">{activeTabTitle}</h2>
          </div>
          
          <div className="flex items-center gap-4">
            <div className="hidden sm:flex items-center gap-1.5 text-[10px] font-bold tracking-widest text-safety-success uppercase">
              <span className="w-2 h-2 rounded-full bg-safety-success animate-pulse" />
              Ingestion pipeline active
            </div>
            <div className="bg-slate-50 border border-safety-border px-3 py-1.5 rounded text-xs font-mono font-bold text-safety-primary select-none">
              {rewards.points.balance} PTS
            </div>
          </div>
        </header>

        {/* Content body */}
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          
          {/* TAB 1: DRIVER HUB (DASHBOARD) */}
          {activeTab === "Dashboard" && (
            <div className="space-y-6">
              
              {/* Asymmetric metrics panel */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                
                {/* Large hero status */}
                <div className="glass-panel p-6 lg:col-span-2 flex flex-col justify-between space-y-4">
                  <div className="space-y-2">
                    <span className="text-[9px] font-bold text-safety-textSecondary uppercase tracking-widest font-mono">Compliance Index Score</span>
                    <div className="flex items-baseline gap-2">
                      <span className="text-5xl font-extrabold text-safety-primary tracking-tight font-sans">{totalScoreAverage}</span>
                      <span className="text-sm font-semibold text-safety-textSecondary">/ 100</span>
                    </div>
                  </div>
                  
                  <div className="space-y-3 pt-2">
                    <p className="text-sm font-medium text-safety-textPrimary">
                      {parseFloat(totalScoreAverage) >= 90.0
                        ? "Excellent compliance rating. Your safety score is in the top tier of regional fleets."
                        : parseFloat(totalScoreAverage) >= 80.0
                        ? "Stable compliance index. Drive alertly to resolve occasional overspeed indicators."
                        : "Focus required. Review overspeed and mobile distractions logged in historical logs."}
                    </p>
                    
                    {/* Integrated milestone streak display */}
                    <div className="space-y-1">
                      <div className="flex justify-between text-[10px] font-bold text-safety-textSecondary uppercase tracking-wide">
                        <span>Milestone: 10 safe trips streak (+100 PTS)</span>
                        <span className="font-mono">{streakVal} / 10</span>
                      </div>
                      <div className="w-full bg-slate-100 h-1.5 rounded-full overflow-hidden border border-safety-border">
                        <div
                          className="bg-safety-primary h-full transition-all duration-300"
                          style={{ width: `${streakProgressPct}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Secondary Streak card */}
                <div className="glass-panel p-6 flex flex-col justify-between">
                  <div className="space-y-1">
                    <span className="text-[9px] font-bold text-safety-textSecondary uppercase tracking-widest font-mono">Streak Records</span>
                    <div className="text-3xl font-extrabold text-safety-textPrimary tracking-tight">{streakVal} Trips</div>
                    <span className="text-[10px] text-safety-textSecondary block uppercase font-mono">Current Safe Interval</span>
                  </div>
                  
                  <div className="border-t border-safety-border pt-4 mt-4 space-y-2">
                    <div className="flex justify-between text-xs">
                      <span className="text-safety-textSecondary">All-Time Peak Streak</span>
                      <span className="font-bold text-safety-textPrimary font-mono">{streaks.longest_streak || 0} Trips</span>
                    </div>
                    <div className="flex justify-between text-xs">
                      <span className="text-safety-textSecondary">Active Streak Bonus</span>
                      <span className="font-bold text-safety-success font-mono">+{streakVal >= 5 ? 50 : 0} PTS</span>
                    </div>
                    <span className="text-[9px] text-safety-textSecondary block italic">Trips below 80 safety score reset safe streaks</span>
                  </div>
                </div>

              </div>

              {/* Core telemetry stats */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
                <div className="glass-panel p-5 space-y-1">
                  <span className="text-[9px] font-bold text-safety-textSecondary uppercase tracking-widest font-mono">Speed Compliance</span>
                  <div className="text-2xl font-extrabold text-safety-textPrimary font-mono">{totalSpeedCompliance}%</div>
                  <span className="text-[10px] text-safety-textSecondary block">Ticks kept within limit bounds</span>
                </div>
                
                <div className="glass-panel p-5 space-y-1">
                  <span className="text-[9px] font-bold text-safety-textSecondary uppercase tracking-widest font-mono">Distraction-Free Rate</span>
                  <div className="text-2xl font-extrabold text-safety-textPrimary font-mono">{totalPhoneFreeCompliance}%</div>
                  <span className="text-[10px] text-safety-textSecondary block">Device secure dock compliance</span>
                </div>
                
                <div className="glass-panel p-5 space-y-1">
                  <span className="text-[9px] font-bold text-safety-textSecondary uppercase tracking-widest font-mono">Sessions Logged</span>
                  <div className="text-2xl font-extrabold text-safety-textPrimary font-mono">{completedTrips.length}</div>
                  <span className="text-[10px] text-safety-textSecondary block">Total compliance runs saved</span>
                </div>
              </div>

              {/* Score Trend & Exceptions log */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                
                {/* Score Trend line chart */}
                <div className="glass-panel p-6 lg:col-span-2 space-y-4">
                  <div className="flex justify-between items-center">
                    <h3 className="text-xs font-bold text-safety-textPrimary uppercase tracking-wider">Compliance Trend</h3>
                    <span className="text-[9px] text-safety-textSecondary uppercase tracking-widest font-mono font-bold">Last 10 Logs</span>
                  </div>
                  <div className="h-[200px] w-full">
                    {completedTrips.length === 0 ? (
                      <div className="h-full flex items-center justify-center text-xs text-safety-textSecondary italic">
                        No compliance data recorded. Complete trips to generate trends.
                      </div>
                    ) : (
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={completedTrips.slice(0, 10).reverse().map((t, i) => ({ name: `#${completedTrips.length - i}`, score: t.safety_score }))}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#F1F3F5" />
                          <XAxis dataKey="name" stroke="#9CA3AF" fontSize={9} />
                          <YAxis stroke="#9CA3AF" fontSize={9} domain={[0, 100]} />
                          <Tooltip contentStyle={{ backgroundColor: "#FFFFFF", borderColor: "#E4E7EB", color: "#111827", fontSize: 11 }} />
                          <Line type="monotone" dataKey="score" stroke="#0F766E" strokeWidth={2} name="Safety Score" dot={{ r: 2 }} />
                        </LineChart>
                      </ResponsiveContainer>
                    )}
                  </div>
                </div>

                {/* Exceptions feed */}
                <div className="glass-panel p-6 flex flex-col justify-between">
                  <div className="space-y-4">
                    <h3 className="text-xs font-bold text-safety-textPrimary uppercase tracking-wider">Recent Ingestion Exceptions</h3>
                    <div className="space-y-2">
                      {globalEvents.slice(0, 3).length === 0 ? (
                        <p className="text-xs text-safety-textSecondary italic py-4">No active compliance exceptions registered in database.</p>
                      ) : (
                        globalEvents.slice(0, 3).map((ev, idx) => (
                          <div key={idx} className="p-3 bg-slate-50 border border-safety-border rounded text-xs space-y-1">
                            <div className="flex justify-between items-center">
                              <span className={`font-bold text-[9px] uppercase tracking-wider ${
                                ev.severity === "HIGH_RISK" ? "text-safety-critical" : "text-safety-warning"
                              }`}>{ev.event_type}</span>
                              <span className="text-[9px] text-safety-textSecondary font-mono">{ev.timestamp}</span>
                            </div>
                            <p className="text-safety-textSecondary text-[10px]">Severity level: {ev.severity}</p>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => setActiveTab("History")}
                    className="mt-4 text-[10px] font-bold text-safety-primary uppercase tracking-widest text-left hover:underline"
                  >
                    Auditing log database →
                  </button>
                </div>

              </div>

            </div>
          )}

          {/* TAB 2: ACTIVE SAFETY HUD */}
          {activeTab === "HUD" && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              
              {/* Telemetry visualizer & manual inputs */}
              <div className="lg:col-span-2 space-y-6">
                
                <VisualizerCanvas
                  telemetry={activeTrip?.ticks || []}
                  currentSpeed={activeTrip?.speed || 0}
                  currentLimit={activeTrip?.speedLimit || 40}
                  riskLevel={activeTrip?.riskLevel || "SAFE"}
                />

                {/* Control Panel */}
                <div className="glass-panel p-6 space-y-6">
                  
                  {/* Mode selector */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-safety-border">
                    <div className="space-y-0.5">
                      <h3 className="text-xs font-bold text-safety-textPrimary uppercase tracking-wider">HUD Ingestion Controller</h3>
                      <p className="text-[10px] text-safety-textSecondary">Configure automatic autopilot parameters or manipulate parameters manually</p>
                    </div>
                    
                    <label className="flex items-center gap-2 select-none cursor-pointer">
                      <input
                        type="checkbox"
                        checked={autopilotEnabled}
                        disabled={isTripRunning}
                        onChange={(e) => setAutopilotEnabled(e.target.checked)}
                        className="rounded border-safety-border text-safety-primary focus:ring-0 w-4 h-4"
                      />
                      <span className="text-xs font-semibold text-safety-textPrimary">Autopilot Simulator Mode</span>
                    </label>
                  </div>

                  {/* Manual Overrides */}
                  <div className={`grid grid-cols-1 sm:grid-cols-3 gap-6 ${isTripRunning ? "opacity-100" : "opacity-45 pointer-events-none"}`}>
                    
                    {/* Speed limits selector */}
                    <div className="space-y-2">
                      <label className="text-[10px] font-bold text-safety-textSecondary uppercase tracking-widest block">Active Speed Limit</label>
                      <select
                        value={manualLimit}
                        onChange={(e) => changeHUDLimit(Number(e.target.value))}
                        className="w-full bg-white border border-safety-border text-xs rounded p-2 focus:outline-none focus:border-safety-primary"
                      >
                        {[30, 40, 50, 60, 80, 100].map(val => (
                          <option key={val} value={val}>{val} KM/H</option>
                        ))}
                      </select>
                    </div>

                    {/* Speed values adjustments */}
                    <div className="space-y-2">
                      <label className="text-[10px] font-bold text-safety-textSecondary uppercase tracking-widest block">Current Speed: <span className="font-mono text-safety-textPrimary">{manualSpeed} km/h</span></label>
                      <div className="flex gap-1">
                        {[-5, -1, 1, 5].map(v => (
                          <button
                            key={v}
                            onClick={() => adjustHUDSpeed(v)}
                            className="flex-1 bg-slate-50 hover:bg-slate-100 border border-safety-border rounded text-[10px] font-bold py-1.5 transition-colors"
                          >
                            {v > 0 ? `+${v}` : v}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Mobile distraction state */}
                    <div className="space-y-2">
                      <label className="text-[10px] font-bold text-safety-textSecondary uppercase tracking-widest block">Mobile Device Dock State</label>
                      <button
                        onClick={() => toggleHUDPhone(!manualPhone)}
                        className={`w-full py-2 px-3 border rounded text-[10px] font-bold uppercase tracking-wider transition-colors ${
                          manualPhone
                            ? "bg-red-50 border-red-200 text-safety-critical hover:bg-red-100"
                            : "bg-green-50 border-green-200 text-safety-success hover:bg-green-100"
                        }`}
                      >
                        {manualPhone ? "Device in Hand (Exception)" : "Device Docked (Secure)"}
                      </button>
                    </div>

                  </div>

                  {/* Playback speed accelerator for testing review */}
                  {isTripRunning && (
                    <div className="flex justify-between items-center bg-slate-50 border border-safety-border p-3 rounded">
                      <span className="text-[10px] text-safety-textSecondary font-bold uppercase tracking-wider">Simulation Speed Factor:</span>
                      <div className="flex gap-1">
                        {[1, 2, 5, 10].map(s => (
                          <button
                            key={s}
                            onClick={() => setPlaybackSpeed(s)}
                            className={`px-3 py-1 text-[10px] font-mono font-bold rounded border ${
                              playbackSpeed === s
                                ? "bg-safety-primary text-white border-safety-primary"
                                : "bg-white text-safety-textPrimary border-safety-border hover:bg-slate-100"
                            }`}
                          >
                            {s}x
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Primary CTA trigger */}
                  <div className="pt-2">
                    {!isTripRunning ? (
                      <button
                        onClick={startIngestionSession}
                        className="w-full py-3 bg-safety-primary text-white hover:bg-teal-700 rounded text-xs font-bold uppercase tracking-widest transition-colors"
                      >
                        Start Compliance Ingestion Session
                      </button>
                    ) : (
                      <button
                        onClick={stopIngestionSession}
                        className="w-full py-3 bg-safety-critical text-white hover:bg-red-700 rounded text-xs font-bold uppercase tracking-widest transition-colors"
                      >
                        Stop and Save Telemetry Record
                      </button>
                    )}
                  </div>

                </div>

              </div>

              {/* Side Dial info Panels */}
              <div className="space-y-6">
                
                {/* Readout stats */}
                <div className="glass-panel p-6 space-y-4">
                  <h3 className="text-xs font-bold text-safety-textPrimary uppercase tracking-wider">Telemetry Readouts</h3>
                  
                  <div className="grid grid-cols-2 gap-4">
                    
                    <div className="bg-slate-50 border border-safety-border p-3.5 rounded">
                      <span className="text-[9px] font-bold text-safety-textSecondary uppercase tracking-widest block mb-1">Safety Index</span>
                      <span className={`text-2xl font-extrabold font-mono ${
                        activeTrip?.riskLevel === "HIGH_RISK" ? "text-safety-critical" :
                        activeTrip?.riskLevel === "WARNING" ? "text-safety-warning" : "text-safety-success"
                      }`}>{activeTrip ? activeTrip.score : 100}</span>
                    </div>

                    <div className="bg-slate-50 border border-safety-border p-3.5 rounded flex items-center justify-between">
                      <div>
                        <span className="text-[9px] font-bold text-safety-textSecondary uppercase tracking-widest block mb-1">Speed</span>
                        <span className="text-xl font-mono font-extrabold text-safety-textPrimary">{activeTrip ? Math.round(activeTrip.speed) : 0} <span className="text-[10px] text-safety-textSecondary font-sans">KM/H</span></span>
                      </div>
                      
                      <div className="w-10 h-10 rounded-full border-[4px] border-red-600 bg-white flex items-center justify-center font-bold font-sans text-xs text-slate-900 select-none">
                        {activeTrip ? activeTrip.speedLimit : 40}
                      </div>
                    </div>

                    <div className="bg-slate-50 border border-safety-border p-3.5 rounded">
                      <span className="text-[9px] font-bold text-safety-textSecondary uppercase tracking-widest block mb-1">Duration elapsed</span>
                      <span className="text-xl font-extrabold font-mono text-safety-textPrimary">
                        {activeTrip
                          ? Math.floor(activeTrip.duration / 60).toString().padStart(2, '0') + ':' + (activeTrip.duration % 60).toString().padStart(2, '0')
                          : "00:00"
                        }
                      </span>
                    </div>

                    <div className="bg-slate-50 border border-safety-border p-3.5 rounded">
                      <span className="text-[9px] font-bold text-safety-textSecondary uppercase tracking-widest block mb-1">Distance logged</span>
                      <span className="text-xl font-extrabold font-mono text-safety-textPrimary">
                        {(activeTrip?.distance || 0).toFixed(2)} km
                      </span>
                    </div>

                  </div>
                </div>

                {/* Coaching Nudge Banner */}
                <div className="glass-panel p-5 space-y-3">
                  <h4 className="text-[10px] font-bold text-safety-textSecondary uppercase tracking-widest">Active Safety Coaching</h4>
                  {activeNudge ? (
                    <div className={`p-4 border rounded text-xs leading-relaxed ${
                      activeNudge.type === "PHONE_WARNING" ? "bg-red-50 border-red-200 text-safety-critical" : "bg-amber-50 border-amber-200 text-safety-warning"
                    }`}>
                      {activeNudge.message}
                    </div>
                  ) : (
                    <div className="text-xs text-safety-success font-medium flex items-center gap-1.5 py-2">
                      <span className="w-2 h-2 rounded-full bg-safety-success" />
                      Ingestion status compliant. No anomalies flagged.
                    </div>
                  )}
                </div>

                {/* Timeline Log */}
                <div className="glass-panel p-6 space-y-4">
                  <h3 className="text-xs font-bold text-safety-textPrimary uppercase tracking-wider">Ingestion Event Stream</h3>
                  <div className="space-y-2 max-h-[160px] overflow-y-auto pr-1">
                    {(!activeTrip || activeTrip.events.length === 0) ? (
                      <p className="text-xs text-safety-textSecondary italic">No live events captured.</p>
                    ) : (
                      activeTrip.events.map((ev, idx) => (
                        <div key={idx} className="p-2.5 bg-slate-50 border border-safety-border rounded text-xs space-y-0.5">
                          <div className="flex justify-between items-center">
                            <span className={`font-bold text-[9px] uppercase tracking-wider ${
                              ev.severity === "HIGH_RISK" ? "text-safety-critical" : "text-safety-warning"
                            }`}>{ev.event_type}</span>
                            <span className="text-[9px] font-mono text-safety-textSecondary">{ev.timestamp}</span>
                          </div>
                          <span className="text-[10px] text-safety-textSecondary">Logged at speed: {Math.round(ev.speed)} km/h</span>
                        </div>
                      ))
                    )}
                  </div>
                </div>

              </div>

            </div>
          )}

          {/* TAB 3: HISTORICAL AUDITS */}
          {activeTab === "History" && (
            <div className="space-y-6">
              
              {/* Simulator state toggles for E2E validation */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 bg-white border border-safety-border rounded-md">
                <div className="space-y-0.5">
                  <h3 className="text-xs font-bold text-safety-textPrimary uppercase tracking-wider font-sans">Audit Database Simulator Controls</h3>
                  <p className="text-[10px] text-safety-textSecondary">Simulate initial state configurations for QA audits</p>
                </div>
                
                <div className="flex gap-4">
                  <label className="flex items-center gap-2 select-none cursor-pointer">
                    <input
                      type="checkbox"
                      checked={simulateEmptyHistory}
                      onChange={(e) => setSimulateEmptyHistory(e.target.checked)}
                      className="rounded border-safety-border text-safety-primary focus:ring-0 w-4 h-4"
                    />
                    <span className="text-xs font-semibold text-safety-textPrimary">Show empty history state</span>
                  </label>
                </div>
              </div>

              {/* Inline detail report view */}
              {selectedReportTrip ? (
                <div className="glass-panel p-6 space-y-6">
                  
                  <div className="flex justify-between items-center pb-4 border-b border-safety-border">
                    <div className="space-y-1">
                      <button
                        onClick={() => setSelectedReportTrip(null)}
                        className="flex items-center gap-1 text-[10px] font-bold text-safety-primary uppercase tracking-widest hover:underline"
                      >
                        <ChevronLeft className="w-3.5 h-3.5" /> Back to History Log
                      </button>
                      <h3 className="text-sm font-bold text-safety-textPrimary uppercase tracking-wider">
                        Compliance Audit Session: {selectedReportTrip.id.slice(0, 16)}
                      </h3>
                    </div>
                    
                    <button
                      onClick={() => deleteTrip(selectedReportTrip.id)}
                      className="px-3 py-1.5 bg-red-50 hover:bg-red-100 border border-red-200 text-safety-critical font-bold text-[10px] uppercase rounded tracking-wider transition-colors"
                    >
                      Delete Log Record
                    </button>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    
                    {/* Column 1: metrics */}
                    <div className="space-y-4">
                      <h4 className="text-[10px] font-bold text-safety-textSecondary uppercase tracking-widest border-b border-slate-100 pb-1">Trip Metrics</h4>
                      
                      <div className="space-y-2.5 text-xs font-mono tabular-nums">
                        <div className="flex justify-between">
                          <span className="text-safety-textSecondary font-sans">Start Timestamp:</span>
                          <span className="text-safety-textPrimary">{selectedReportTrip.start_time}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-safety-textSecondary font-sans">End Timestamp:</span>
                          <span className="text-safety-textPrimary">{selectedReportTrip.end_time}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-safety-textSecondary font-sans">Ingested Duration:</span>
                          <span className="text-safety-textPrimary">{selectedReportTrip.duration_seconds} seconds</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-safety-textSecondary font-sans">Ingested Distance:</span>
                          <span className="text-safety-textPrimary">{selectedReportTrip.distance_km.toFixed(2)} km</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-safety-textSecondary font-sans">Average / Max Speed:</span>
                          <span className="text-safety-textPrimary">{Math.round(selectedReportTrip.avg_speed)} / {Math.round(selectedReportTrip.max_speed)} km/h</span>
                        </div>
                      </div>
                    </div>

                    {/* Column 2: compliance */}
                    <div className="space-y-4">
                      <h4 className="text-[10px] font-bold text-safety-textSecondary uppercase tracking-widest border-b border-slate-100 pb-1">Compliance Evaluations</h4>
                      
                      <div className="space-y-2.5 text-xs font-mono">
                        <div className="flex justify-between">
                          <span className="text-safety-textSecondary font-sans">Safety Index Score:</span>
                          <span className={`font-bold ${
                            selectedReportTrip.safety_score >= 90 ? "text-safety-success" :
                            selectedReportTrip.safety_score >= 80 ? "text-safety-warning" : "text-safety-critical"
                          }`}>{selectedReportTrip.safety_score} / 100</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-safety-textSecondary font-sans">Speed Compliance Rate:</span>
                          <span className="text-safety-textPrimary">{selectedReportTrip.speed_compliance_pct.toFixed(0)}%</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-safety-textSecondary font-sans">Distraction-Free Rate:</span>
                          <span className="text-safety-textPrimary">{selectedReportTrip.phone_free_pct.toFixed(0)}%</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-safety-textSecondary font-sans">Deduction Credits:</span>
                          <span className="text-safety-success font-bold font-mono">+{selectedReportTrip.points_earned} PTS</span>
                        </div>
                      </div>
                    </div>

                    {/* Column 3: Event history */}
                    <div className="space-y-4 md:col-span-3">
                      <h4 className="text-[10px] font-bold text-safety-textSecondary uppercase tracking-widest border-b border-slate-100 pb-1">Ingested Anomalies Timeline</h4>
                      
                      <div className="space-y-2 max-h-[220px] overflow-y-auto">
                        {selectedTripEvents.length === 0 ? (
                          <p className="text-xs text-safety-textSecondary italic py-3">No compliance exceptions were logged during this trip.</p>
                        ) : (
                          selectedTripEvents.map((ev, idx) => (
                            <div key={idx} className="p-3 bg-slate-50 border border-safety-border rounded text-xs flex justify-between items-start gap-4">
                              <div className="space-y-0.5">
                                <span className={`font-bold text-[9px] uppercase tracking-wider ${
                                  ev.severity === "HIGH_RISK" ? "text-safety-critical" : "text-safety-warning"
                                }`}>{ev.event_type}</span>
                                <p className="text-[10px] text-safety-textSecondary">
                                  Evaluated speed: {Math.round(ev.speed)} km/h (Limit: {Math.round(ev.speed_limit)} km/h)
                                </p>
                              </div>
                              <span className="text-[10px] font-mono text-safety-textSecondary">{ev.timestamp}</span>
                            </div>
                          ))
                        )}
                      </div>
                    </div>

                  </div>

                </div>
              ) : (
                <div className="glass-panel overflow-hidden">
                  
                  {/* Table header sort filters */}
                  <div className="p-4 border-b border-safety-border flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-safety-textSecondary uppercase tracking-wider font-bold">Sort Audit Index:</span>
                      <select
                        value={historySort}
                        onChange={(e) => {
                          setHistorySort(e.target.value);
                          loadTripHistory(e.target.value);
                        }}
                        className="bg-white border border-safety-border text-xs rounded px-2.5 py-1 focus:outline-none focus:border-safety-primary"
                      >
                        <option value="Latest">Latest Date/Time</option>
                        <option value="Highest Safety Score">Highest Safety Score</option>
                        <option value="Lowest Safety Score">Lowest Safety Score</option>
                        <option value="Longest Trip">Longest Distance</option>
                      </select>
                    </div>
                    
                    <span className="text-[10px] font-mono font-bold text-safety-textSecondary uppercase tracking-widest">
                      Total Indexed Records: {renderTripsList.length}
                    </span>
                  </div>

                  {renderTripsList.length === 0 ? (
                    <div className="p-12 text-center space-y-2">
                      <p className="text-sm font-semibold text-safety-textPrimary">Compliance Database Empty</p>
                      <p className="text-xs text-safety-textSecondary max-w-sm mx-auto">
                        No historical telemetry records found. Navigate to the Active Safety HUD tab and complete an ingestion session to populate records for audit compliance review.
                      </p>
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left border-collapse text-xs">
                        <thead className="bg-slate-50 border-b border-safety-border uppercase tracking-widest text-[9px] text-safety-textSecondary font-bold">
                          <tr>
                            <th className="p-3">Date/Time</th>
                            <th className="p-3">Ingestion Mode</th>
                            <th className="p-3 text-right">Duration</th>
                            <th className="p-3 text-right">Distance</th>
                            <th className="p-3 text-right">Max/Avg Speed</th>
                            <th className="p-3 text-right">Safety Score</th>
                            <th className="p-3 text-right">Credits</th>
                            <th className="p-3 text-center">Actions</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 font-mono tabular-nums text-safety-textPrimary">
                          {renderTripsList.map((trip) => (
                            <tr key={trip.id} className="hover:bg-slate-50/50">
                              <td className="p-3 font-semibold text-safety-textPrimary font-sans">
                                <div>{trip.id.slice(5, 15).replace("_", " ")}</div>
                                <div className="text-[8px] text-safety-textSecondary font-mono">{trip.id}</div>
                              </td>
                              <td className="p-3 font-semibold text-safety-textSecondary font-sans uppercase text-[9px]">{trip.mode}</td>
                              <td className="p-3 text-right">{trip.duration_seconds}s</td>
                              <td className="p-3 text-right">{trip.distance_km.toFixed(2)} km</td>
                              <td className="p-3 text-right">{Math.round(trip.max_speed)} / {Math.round(trip.avg_speed)} km/h</td>
                              <td className="p-3 text-right">
                                <span className={`font-bold px-2 py-0.5 rounded text-[10px] font-sans ${
                                  trip.safety_score >= 90 ? "bg-green-50 border border-green-200 text-safety-success" :
                                  trip.safety_score >= 80 ? "bg-amber-50 border border-amber-200 text-safety-warning" : "bg-red-50 border border-red-200 text-safety-critical"
                                }`}>
                                  {trip.safety_score}
                                </span>
                              </td>
                              <td className="p-3 text-right text-safety-primary font-bold font-sans">+{trip.points_earned} PTS</td>
                              <td className="p-3 text-center font-sans">
                                <button
                                  onClick={() => {
                                    setSelectedReportTrip(trip);
                                    api.getTripEvents(trip.id).then(evts => setSelectedTripEvents(evts));
                                  }}
                                  className="text-safety-primary font-bold hover:underline"
                                >
                                  View Audit
                                </button>
                                <button
                                  onClick={() => deleteTrip(trip.id)}
                                  className="text-safety-critical font-bold hover:text-red-700 ml-3"
                                >
                                  Delete
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                </div>
              )}

            </div>
          )}

          {/* TAB 4: LEADERBOARD */}
          {activeTab === "Leaderboard" && (
            <div className="space-y-6">
              
              {/* Simulator Switch */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 bg-white border border-safety-border rounded-md">
                <div className="space-y-0.5">
                  <h3 className="text-xs font-bold text-safety-textPrimary uppercase tracking-wider font-sans">Leaderboard Simulator Controls</h3>
                  <p className="text-[10px] text-safety-textSecondary">Simulate limited pod sizes for interface evaluation</p>
                </div>
                
                <label className="flex items-center gap-2 select-none cursor-pointer">
                  <input
                    type="checkbox"
                    checked={simulateSmallPod}
                    onChange={(e) => setSimulateSmallPod(e.target.checked)}
                    className="rounded border-safety-border text-safety-primary focus:ring-0 w-4 h-4"
                  />
                  <span className="text-xs font-semibold text-safety-textPrimary">Show partial pod state</span>
                </label>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                
                {/* Left card: Regional Standings */}
                <div className="glass-panel p-6 space-y-4">
                  <div className="space-y-1">
                    <h3 className="text-xs font-bold text-safety-textPrimary uppercase tracking-wider">Regional Pod Standings</h3>
                    <p className="text-[10px] text-safety-textSecondary">Average compliance scores for active driver peer teams</p>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead className="bg-slate-50 border-b border-safety-border uppercase text-[9px] font-bold text-safety-textSecondary">
                        <tr>
                          <th className="p-3">Rank</th>
                          <th className="p-3">Pod Name</th>
                          <th className="p-3 text-right">Reputation Score</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 font-mono text-safety-textPrimary">
                        {[
                          { rank: 1, name: "SAFE CRUISERS", score: 95, size: 5 },
                          { rank: 2, name: "ROAD GUARDIANS", score: peerPod.reputation, size: podMembers.length },
                          { rank: 3, name: "ECO FLYERS", score: 87, size: 6 },
                          { rank: 4, name: "CITY SHIELD", score: 82, size: 8 }
                        ].sort((a,b) => b.score - a.score).map((pod, i) => (
                          <tr key={pod.name} className="hover:bg-slate-50/50">
                            <td className="p-3 font-bold font-sans">#{i + 1}</td>
                            <td className="p-3 font-semibold text-safety-textPrimary font-sans">
                              {pod.name} <span className="text-[10px] text-safety-textSecondary font-normal">({pod.size} drivers)</span>
                            </td>
                            <td className="p-3 text-right text-safety-primary font-bold">{pod.score} PTS</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Right card: Pod members list */}
                <div className="glass-panel p-6 space-y-4">
                  <div className="space-y-1">
                    <h3 className="text-xs font-bold text-safety-textPrimary uppercase tracking-wider">ROAD GUARDIANS: Driver Standings</h3>
                    <p className="text-[10px] text-safety-textSecondary">Weekly score and safe credits breakdown</p>
                  </div>

                  <div className="space-y-3">
                    {podMembers.map((member, idx) => {
                      const displayName = member.is_user ? `${user.name} (You)` : member.member_name;
                      return (
                        <div
                          key={member.id || idx}
                          className={`flex items-center justify-between p-3 border rounded transition-colors ${
                            member.is_user
                              ? "bg-teal-50/40 border-safety-primary/40"
                              : "bg-white border-safety-border hover:bg-slate-50/40"
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <span className="font-bold text-xs text-safety-textSecondary font-mono w-4">#{idx + 1}</span>
                            <div className="space-y-0.5">
                              <span className="truncate block max-w-[200px] font-sans font-semibold text-xs text-safety-textPrimary" title={displayName}>
                                {displayName}
                              </span>
                              <span className="text-[10px] text-safety-textSecondary font-mono block">Streak: {member.streak || 0} Trips</span>
                            </div>
                          </div>
                          <div className="text-right">
                            <span className="text-xs font-bold text-safety-textPrimary font-mono block">{member.weekly_score} Score</span>
                            <span className="text-[9px] text-safety-success font-bold font-mono">+{member.contribution} Contribution</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* Cooperative Feedback */}
                  <div className="bg-slate-50 border border-safety-border p-3 rounded mt-2">
                    <span className="text-[9px] font-bold text-safety-textSecondary uppercase tracking-widest block mb-1">Cooperative Performance</span>
                    <p className="text-xs text-safety-textPrimary leading-relaxed">{peerPod.social_feedback}</p>
                  </div>
                </div>

              </div>

            </div>
          )}

          {/* TAB 5: REWARDS */}
          {activeTab === "Rewards" && (
            <div className="space-y-6">
              
              {/* Points Ledger Card */}
              <div className="glass-panel p-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-6">
                <div className="space-y-1">
                  <span className="text-[9px] font-bold text-safety-textSecondary uppercase tracking-widest font-mono">Available Points Balance</span>
                  <div className="text-4xl font-extrabold text-safety-primary tracking-tight font-sans">
                    {rewards.points.balance} <span className="text-sm font-semibold text-safety-textSecondary">PTS</span>
                  </div>
                </div>
                
                <div className="border-t sm:border-t-0 sm:border-l border-safety-border pt-4 sm:pt-0 sm:pl-6 space-y-1 text-xs">
                  <div className="flex justify-between sm:gap-12">
                    <span className="text-safety-textSecondary">Total compliance credits accumulated:</span>
                    <span className="font-bold text-safety-textPrimary font-mono">{rewards.points.total_earned} PTS</span>
                  </div>
                  <div className="flex justify-between sm:gap-12">
                    <span className="text-safety-textSecondary">Milestone bonus points earned:</span>
                    <span className="font-bold text-safety-success font-mono">+{completedTrips.filter(t => t.safety_score === 100).length * 10} PTS</span>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                
                {/* Available redemptions */}
                <div className="glass-panel p-6 space-y-4">
                  <div className="space-y-1">
                    <h3 className="text-xs font-bold text-safety-textPrimary uppercase tracking-wider">Benefit Redemptions Catalog</h3>
                    <p className="text-[10px] text-safety-textSecondary">Redeem points for active fleet driver benefits</p>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {rewards.catalog.map((item) => {
                      const canRedeem = rewards.points.balance >= item.cost_points;
                      return (
                        <div key={item.id} className="border border-safety-border p-4 rounded flex flex-col justify-between space-y-4 bg-white">
                          <div className="space-y-1">
                            <h4 className="font-semibold text-xs text-safety-textPrimary">{item.name}</h4>
                            <p className="text-[10px] text-safety-textSecondary">{item.description}</p>
                          </div>
                          
                          <div className="flex items-center justify-between pt-2">
                            <span className="text-xs font-bold font-mono text-safety-primary">{item.cost_points} PTS</span>
                            <button
                              disabled={!canRedeem}
                              onClick={() => redeemReward(item.id)}
                              className={`px-3 py-1.5 rounded text-[10px] font-bold uppercase tracking-wider transition-colors ${
                                canRedeem
                                  ? "bg-safety-primary text-white hover:bg-teal-700"
                                  : "bg-slate-100 text-safety-textSecondary border border-safety-border cursor-not-allowed"
                              }`}
                            >
                              Redeem
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Redemption Audit Log */}
                <div className="glass-panel p-6 space-y-4">
                  <div className="space-y-1">
                    <h3 className="text-xs font-bold text-safety-textPrimary uppercase tracking-wider">Redemption Audit Log</h3>
                    <p className="text-[10px] text-safety-textSecondary">Historical ledger of redeemed vouchers</p>
                  </div>

                  {redemptions.length === 0 ? (
                    <p className="text-xs text-safety-textSecondary italic py-8 text-center">No redemptions logged yet.</p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs border-collapse">
                        <thead className="bg-slate-50 border-b border-safety-border uppercase text-[9px] font-bold text-safety-textSecondary">
                          <tr>
                            <th className="p-3">Claim Benefit</th>
                            <th className="p-3 text-right">Points Cost</th>
                            <th className="p-3 text-right">Timestamp</th>
                            <th className="p-3 text-center">Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100 font-mono tabular-nums text-safety-textPrimary">
                          {redemptions.map((red) => (
                            <tr key={red.id} className="hover:bg-slate-50/50">
                              <td className="p-3 font-semibold text-safety-textPrimary font-sans">{red.name}</td>
                              <td className="p-3 text-right text-safety-primary font-bold">-{red.cost_points} PTS</td>
                              <td className="p-3 text-right text-safety-textSecondary">{red.redeemed_at.slice(0, 19).replace("T", " ")}</td>
                              <td className="p-3 text-center text-safety-success font-bold uppercase text-[9px] font-sans">{red.status}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>

              </div>

            </div>
          )}

          {/* TAB 6: PROFILE & SETTINGS */}
          {activeTab === "Profile" && (
            <div className="space-y-6">
              
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                
                {/* Driver Account Panel */}
                <div className="glass-panel p-6 space-y-6 lg:col-span-2">
                  <div className="space-y-1 pb-4 border-b border-safety-border">
                    <h3 className="text-xs font-bold text-safety-textPrimary uppercase tracking-wider">Driver Profile Settings</h3>
                    <p className="text-[10px] text-safety-textSecondary">Update your driver identification details and account security credentials</p>
                  </div>

                  <form onSubmit={handleProfileUpdate} className="space-y-6">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div>
                        <label className="block text-[10px] font-bold text-safety-textSecondary uppercase tracking-widest mb-1.5">Driver Name</label>
                        <input
                          type="text"
                          required
                          value={profileName}
                          onChange={(e) => setProfileName(e.target.value)}
                          className="w-full bg-slate-50 border border-safety-border text-xs rounded p-2.5 text-slate-900 focus:outline-none focus:border-safety-primary focus:bg-white transition-colors"
                        />
                      </div>
                      
                      <div>
                        <label className="block text-[10px] font-bold text-safety-textSecondary uppercase tracking-widest mb-1.5">Email Address</label>
                        <input
                          type="email"
                          disabled
                          value={user.email}
                          className="w-full bg-slate-100 border border-safety-border text-xs rounded p-2.5 text-safety-textSecondary cursor-not-allowed"
                        />
                      </div>
                    </div>

                    <div className="border-t border-safety-border pt-4 space-y-4">
                      <h4 className="text-[10px] font-bold text-safety-textSecondary uppercase tracking-widest">Update Password</h4>
                      
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                          <label className="block text-[10px] font-bold text-safety-textSecondary uppercase tracking-widest mb-1.5">Old Password</label>
                          <input
                            type="password"
                            value={profileOldPassword}
                            onChange={(e) => setProfileOldPassword(e.target.value)}
                            placeholder="Enter old password..."
                            className="w-full bg-slate-50 border border-safety-border text-xs rounded p-2.5 text-slate-900 focus:outline-none focus:border-safety-primary focus:bg-white transition-colors"
                          />
                        </div>
                        
                        <div>
                          <label className="block text-[10px] font-bold text-safety-textSecondary uppercase tracking-widest mb-1.5">New Password</label>
                          <input
                            type="password"
                            value={profilePassword}
                            onChange={(e) => setProfilePassword(e.target.value)}
                            placeholder="Enter new password..."
                            className="w-full bg-slate-50 border border-safety-border text-xs rounded p-2.5 text-slate-900 focus:outline-none focus:border-safety-primary focus:bg-white transition-colors"
                          />
                        </div>
                      </div>
                    </div>

                    <div className="border-t border-safety-border pt-4 space-y-4">
                      <h4 className="text-[10px] font-bold text-safety-textSecondary uppercase tracking-widest">Compliance Limits Configuration</h4>
                      
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                        <div>
                          <label className="block text-[10px] font-bold text-safety-textSecondary uppercase tracking-widest mb-1.5">Warning Threshold (KM/H)</label>
                          <input
                            type="number"
                            value={settings.warning_threshold}
                            onChange={(e) => setSettings({ ...settings, warning_threshold: parseInt(e.target.value) || 0 })}
                            className="w-full bg-slate-50 border border-safety-border text-xs rounded p-2.5 text-slate-900 focus:outline-none focus:border-safety-primary focus:bg-white transition-colors"
                          />
                        </div>

                        <div>
                          <label className="block text-[10px] font-bold text-safety-textSecondary uppercase tracking-widest mb-1.5">Critical Threshold (KM/H)</label>
                          <input
                            type="number"
                            value={settings.critical_threshold}
                            onChange={(e) => setSettings({ ...settings, critical_threshold: parseInt(e.target.value) || 0 })}
                            className="w-full bg-slate-50 border border-safety-border text-xs rounded p-2.5 text-slate-900 focus:outline-none focus:border-safety-primary focus:bg-white transition-colors"
                          />
                        </div>

                        <div>
                          <label className="block text-[10px] font-bold text-safety-textSecondary uppercase tracking-widest mb-1.5">Data Retention (Days)</label>
                          <input
                            type="number"
                            value={settings.privacy_data_retention_days}
                            onChange={(e) => setSettings({ ...settings, privacy_data_retention_days: parseInt(e.target.value) || 30 })}
                            className="w-full bg-slate-50 border border-safety-border text-xs rounded p-2.5 text-slate-900 focus:outline-none focus:border-safety-primary focus:bg-white transition-colors"
                          />
                        </div>
                      </div>
                    </div>

                    <div className="flex justify-end pt-4 border-t border-safety-border">
                      <button
                        type="submit"
                        className="px-6 py-2.5 bg-safety-primary text-white hover:bg-teal-700 rounded text-xs font-bold uppercase tracking-widest transition-colors"
                      >
                        Save Profile & Settings
                      </button>
                    </div>
                  </form>
                </div>

                {/* Right Side: Parental Notifications and logs */}
                <div className="space-y-6">
                  
                  {/* Guardian Email Controls */}
                  <div className="glass-panel p-6 space-y-4">
                    <div className="space-y-1">
                      <h3 className="text-xs font-bold text-safety-textPrimary uppercase tracking-wider flex items-center gap-2">
                        <Mail className="w-4 h-4 text-safety-primary" />
                        Guardian Alerts
                      </h3>
                      <p className="text-[10px] text-safety-textSecondary">Receive automatic email reports when severe infractions are logged.</p>
                    </div>
                    
                    {isEmailJSDemoMode && (
                      <div className="p-3 bg-amber-50 border border-amber-200 rounded text-[10px] text-amber-800 leading-relaxed">
                        <strong>Demo Mode Active:</strong> Real-time emails require configuration. Create a <code>.env</code> file in your <code>frontend/</code> directory with your <code>VITE_EMAILJS_PUBLIC_KEY</code> to enable live delivery.
                      </div>
                    )}
                    
                    <div className="space-y-3">
                      <div>
                        <label className="block text-[10px] font-bold text-safety-textSecondary uppercase tracking-widest mb-1.5">Guardian Email Address</label>
                        <input
                          type="email"
                          placeholder="guardian@email.com"
                          className="w-full bg-slate-50 border border-safety-border text-xs rounded p-2.5 text-slate-900 focus:outline-none focus:border-safety-primary"
                          value={settings.parent_email || ""}
                          onChange={(e) => setSettings({ ...settings, parent_email: e.target.value })}
                        />
                      </div>

                      <label className="flex items-center gap-2 select-none cursor-pointer pt-2">
                        <input
                          type="checkbox"
                          checked={!!settings.guardian_enabled}
                          onChange={(e) => setSettings({ ...settings, guardian_enabled: e.target.checked })}
                          className="rounded border-safety-border text-safety-primary focus:ring-0 w-4 h-4"
                        />
                        <span className="text-xs font-semibold text-safety-textPrimary">Enable Live Guardian Notification Alerts</span>
                      </label>
                    </div>
                  </div>

                  {/* Parental Alert Log & Manual Queue Retry */}
                  <div className="glass-panel p-6 space-y-4 flex flex-col justify-between">
                    <div className="space-y-4">
                      <div className="flex justify-between items-center border-b border-slate-100 pb-2">
                        <h3 className="text-xs font-bold text-safety-textPrimary uppercase tracking-wider">Guardian Mail Transmission Log</h3>
                        <button
                          onClick={handleRetryNotifications}
                          className="flex items-center gap-1.5 px-2.5 py-1 bg-teal-50 hover:bg-teal-100 border border-safety-primary/30 rounded text-[10px] font-bold text-safety-primary uppercase tracking-wider transition-colors"
                        >
                          <RefreshCw className="w-3 h-3" />
                          Retry Queue
                        </button>
                      </div>

                      <div className="space-y-2 max-h-[220px] overflow-y-auto pr-1">
                        {notificationsHistory.length === 0 ? (
                          <p className="text-xs text-safety-textSecondary italic py-4 text-center">No alerts have been queued or transmitted.</p>
                        ) : (
                          notificationsHistory.map((log) => (
                            <div key={log.id} className="p-3 bg-slate-50 border border-safety-border rounded text-xs space-y-1.5">
                              <div className="flex justify-between items-center">
                                <span className="font-bold text-[9px] uppercase tracking-wider text-safety-textPrimary">
                                  {log.event_type}
                                </span>
                                <span className={`font-mono text-[9px] font-bold px-1.5 py-0.5 rounded ${
                                  log.status === "SENT" ? "bg-green-50 text-safety-success" : "bg-amber-50 text-safety-warning"
                                }`}>
                                  {log.status}
                                </span>
                              </div>
                              
                              <p className="text-[10px] text-safety-textSecondary font-mono truncate">
                                Recipient: {log.recipient}
                              </p>
                              
                              <div className="flex justify-between items-center text-[9px] text-safety-textSecondary font-mono pt-1">
                                <span>Time: {log.timestamp.slice(11, 19)}</span>
                                {log.status === "QUEUED" && (
                                  <span className="text-safety-warning animate-pulse">Pending connection retry</span>
                                )}
                              </div>
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  </div>

                </div>

              </div>

            </div>
          )}

        </main>
      </div>

      {/* FINAL TRIP SUMMARY MODAL */}
      {activeTrip?.finalSummary && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/35">
          <div className="bg-white border border-safety-border rounded-md max-w-md w-full p-6 space-y-6 shadow-sm">
            
            <div className="flex justify-between items-center pb-3 border-b border-safety-border">
              <h3 className="text-sm font-bold text-safety-textPrimary uppercase tracking-wider">Ingestion Session Finalized</h3>
              <button
                onClick={() => {
                  setActiveTrip(null);
                  setActiveTab("History");
                }}
              >
                <X className="w-4 h-4 text-safety-textSecondary hover:text-safety-textPrimary" />
              </button>
            </div>

            <div className="space-y-4">
              <p className="text-xs text-safety-textSecondary">
                Telemetry record has been compiled and committed to the SQLite database. Compliance metrics results:
              </p>
              
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-slate-50 border border-safety-border p-3 rounded">
                  <span className="text-[9px] font-bold text-safety-textSecondary uppercase tracking-widest block mb-0.5">Safety Index Score</span>
                  <span className={`text-xl font-bold font-mono ${
                    activeTrip.finalSummary.safety_score >= 90 ? "text-safety-success" :
                    activeTrip.finalSummary.safety_score >= 80 ? "text-safety-warning" : "text-safety-critical"
                  }`}>{activeTrip.finalSummary.safety_score} / 100</span>
                </div>

                <div className="bg-slate-50 border border-safety-border p-3 rounded">
                  <span className="text-[9px] font-bold text-safety-textSecondary uppercase tracking-widest block mb-0.5">Credits Awarded</span>
                  <span className="text-xl font-bold font-mono text-safety-primary">+{activeTrip.finalSummary.points_earned} PTS</span>
                </div>

                <div className="bg-slate-50 border border-safety-border p-3 rounded">
                  <span className="text-[9px] font-bold text-safety-textSecondary uppercase tracking-widest block mb-0.5">Duration Logged</span>
                  <span className="text-xl font-bold font-mono text-safety-textPrimary">{activeTrip.finalSummary.duration_seconds}s</span>
                </div>

                <div className="bg-slate-50 border border-safety-border p-3 rounded">
                  <span className="text-[9px] font-bold text-safety-textSecondary uppercase tracking-widest block mb-0.5">Distance Logged</span>
                  <span className="text-xl font-bold font-mono text-safety-textPrimary">{activeTrip.finalSummary.distance_km.toFixed(2)} km</span>
                </div>
              </div>

              {activeTrip.streakResult && (
                <div className="bg-teal-50/40 border border-safety-primary/30 p-3.5 rounded text-xs">
                  <span className="font-bold text-safety-primary block mb-0.5">Safe Streak Progress</span>
                  <p className="text-safety-textPrimary">
                    You've reached a streak of <span className="font-bold">{activeTrip.streakResult.current_streak} safe trips</span>!
                    {activeTrip.streakResult.current_streak >= 10
                      ? " 🏆 Milestone reached: 10 safe trips (+100 PTS milestone bonus applied)."
                      : ` Get to 10 consecutive trips to claim the next milestone bonus.`}
                  </p>
                </div>
              )}
            </div>

            <button
              onClick={() => {
                setActiveTrip(null);
                setActiveTab("History");
              }}
              className="w-full py-2.5 bg-safety-primary text-white hover:bg-teal-700 rounded text-xs font-bold uppercase tracking-wider transition-colors"
            >
              Close and View History
            </button>

          </div>
        </div>
      )}

      {toast && (
        <div 
          style={{
            position: 'fixed',
            bottom: '24px',
            right: '24px',
            zIndex: 9999,
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            padding: '12px 18px',
            borderRadius: '8px',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
            border: '1px solid',
            transition: 'all 0.3s ease-in-out'
          }}
          className={
            toast.type === "success" 
              ? "bg-teal-50 border-teal-200 text-teal-900" 
              : toast.type === "error"
              ? "bg-rose-50 border-rose-200 text-rose-900"
              : "bg-amber-50 border-amber-200 text-amber-900"
          }
        >
          {toast.type === "success" ? (
            <div className="bg-teal-500 text-white p-1 rounded-full"><Check className="w-3.5 h-3.5" /></div>
          ) : (
            <div className="bg-rose-500 text-white p-1 rounded-full"><AlertTriangle className="w-3.5 h-3.5" /></div>
          )}
          <div className="flex flex-col">
            <span className="text-xs font-bold">{toast.type === "success" ? "Notification Sent" : "Transmission Status"}</span>
            <span className="text-[10px] opacity-80">{toast.message}</span>
          </div>
          <button onClick={() => setToast(null)} className="ml-2 hover:opacity-75 p-1 rounded-full hover:bg-black/5">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

    </div>
  );
}
