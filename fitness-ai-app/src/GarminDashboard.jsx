import { useCallback, useEffect, useMemo, useState } from "react";
import Navbar from "./Navbar.jsx";
import "./GarminDashboard.css";
import { connectGarminTest, fetchGarminDashboard } from "./lib/api.js";
import { useAuth } from "./auth/AuthContext.jsx";

function formatDistanceKm(meters) {
  if (typeof meters !== "number") return "-";
  return `${(meters / 1000).toFixed(2)} km`;
}

function formatDuration(seconds) {
  if (typeof seconds !== "number") return "-";
  const total = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(total / 3600);
  const mins = Math.floor((total % 3600) / 60);
  if (hours > 0) return `${hours}h ${mins}m`;
  return `${mins}m`;
}

export default function GarminDashboard() {
  const { isAuthenticated, token, user, connectService } = useAuth();
  const [loading, setLoading] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [dashboard, setDashboard] = useState(null);
  const [error, setError] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const loadDashboard = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError("");
    try {
      const data = await fetchGarminDashboard(token);
      if (!data?.connected) {
        setDashboard(null);
        setError(data?.error || "Garmin is not connected yet.");
      } else {
        setDashboard(data.dashboard || null);
      }
    } catch (err) {
      setDashboard(null);
      setError(err?.message || "Unable to load Garmin dashboard right now.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  const cards = useMemo(() => {
    const data = dashboard || {};
    return [
      { label: "Steps", value: data.steps ?? "-" },
      { label: "Calories", value: data.calories ?? "-" },
      { label: "Active Calories", value: data.activeCalories ?? "-" },
      { label: "Distance", value: formatDistanceKm(data.distanceMeters) },
      { label: "Sleep", value: typeof data.sleepHours === "number" ? `${data.sleepHours} h` : "-" },
      { label: "Date", value: data.date || "-" },
    ];
  }, [dashboard]);

  const handleConnectWithEnv = async () => {
    setConnecting(true);
    setError("");
    try {
      await connectService("garmin");
      await loadDashboard();
    } catch (err) {
      setError(err?.message || "Garmin connect failed.");
    } finally {
      setConnecting(false);
    }
  };

  const handleConnectWithForm = async (event) => {
    event.preventDefault();
    if (!token) return;
    setConnecting(true);
    setError("");
    try {
      await connectGarminTest(token, { email, password });
      setPassword("");
      await loadDashboard();
    } catch (err) {
      setError(err?.message || "Garmin connect failed with provided credentials.");
    } finally {
      setConnecting(false);
    }
  };

  return (
    <div className="app">
      <Navbar />

      <div className="garmin-page">
        <div className="garmin-header">
          <span className="garmin-badge">Garmin Connect</span>
          <h1>Garmin Health Dashboard</h1>
          <p>See your latest steps, calories, sleep metrics, and recent trainings.</p>
        </div>

        {!isAuthenticated ? (
          <div className="garmin-panel">
            <h3>Please log in first</h3>
            <p>You need to be logged in to connect Garmin and load your data.</p>
          </div>
        ) : (
          <>
            <div className="garmin-panel garmin-connect-panel">
              <h3>Connection</h3>
              <p className="garmin-muted">
                Current account: <strong>{user?.email || "unknown"}</strong>
              </p>
              <div className="garmin-connect-actions">
                <button type="button" className="save-btn" onClick={handleConnectWithEnv} disabled={connecting}>
                  {connecting ? "Connecting..." : "Connect Garmin (.env creds)"}
                </button>
                <button type="button" className="save-btn" onClick={loadDashboard} disabled={loading}>
                  {loading ? "Refreshing..." : "Refresh dashboard"}
                </button>
              </div>

              <form className="garmin-form" onSubmit={handleConnectWithForm}>
                <label>
                  Garmin email
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="name@example.com"
                    autoComplete="username"
                  />
                </label>
                <label>
                  Garmin password
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Use only for testing"
                    autoComplete="current-password"
                  />
                </label>
                <button type="submit" className="save-btn" disabled={connecting || !email || !password}>
                  {connecting ? "Testing..." : "Connect with typed credentials"}
                </button>
              </form>

              {error && <p className="garmin-error">{error}</p>}
            </div>

            <div className="garmin-grid">
              {cards.map((card) => (
                <div key={card.label} className="garmin-card">
                  <span>{card.label}</span>
                  <strong>{card.value}</strong>
                </div>
              ))}
            </div>

            <div className="garmin-panel">
              <h3>Recent trainings</h3>
              {Array.isArray(dashboard?.activities) && dashboard.activities.length > 0 ? (
                <div className="garmin-activities">
                  {dashboard.activities.map((activity, index) => (
                    <article key={`${activity.name}-${activity.start || index}`} className="garmin-activity">
                      <h4>{activity.name || "Activity"}</h4>
                      <p>{activity.start || "Unknown time"}</p>
                      <div className="garmin-activity-metrics">
                        <span>Duration: {formatDuration(activity.durationSeconds)}</span>
                        <span>Calories: {activity.calories ?? "-"}</span>
                        <span>Distance: {formatDistanceKm(activity.distanceMeters)}</span>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="garmin-muted">No recent activities were returned for this account.</p>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

