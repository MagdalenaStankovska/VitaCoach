import { NavLink } from "react-router-dom";
import "./Navbar.css";
import { useAuth } from "./auth/AuthContext.jsx";

export default function Navbar() {
  const { isAuthenticated, user, connectService, logout } = useAuth();
  const googleConnected = Boolean(user?.googleCalendarConnected);
  const garminConnected = Boolean(user?.garminConnected);

  const handleConnect = async (serviceName) => {
    try {
      await connectService(serviceName);
    } catch (error) {
      window.alert(error?.message || "Unable to connect the selected service right now.");
    }
  };

  return (
    <div className="navbar">
      <NavLink to="/" className="logo" style={{ textDecoration: "none" }}>
        💚 VitaCoach AI
      </NavLink>

      <div className="menu">
        <NavLink to="/trainings" className="nav-link">Trainings</NavLink>
        <NavLink to="/" end className="nav-link">AI Coach</NavLink>
        <NavLink to="/my-plan" className="nav-link">My Plan</NavLink>
        {isAuthenticated && (
          <NavLink to="/schedule" className="nav-link">📅 Schedule</NavLink>
        )}
        {isAuthenticated && (
          <NavLink to="/garmin" className="nav-link">⌚ Garmin</NavLink>
        )}
        {isAuthenticated ? (
          <>
            {/* Preferences page link added to header menu so the user can open it quickly */}
            <NavLink to="/preferences" className="nav-link">⚙️ Preferences</NavLink>
            <button type="button" className="nav-link nav-action" onClick={logout}>
              Log out
            </button>
          </>
        ) : (
          <>
            <NavLink to="/login" className="nav-link">Log in</NavLink>
            <NavLink to="/register" className="nav-link">Register</NavLink>
          </>
        )}
      </div>
    </div>
  );
}
