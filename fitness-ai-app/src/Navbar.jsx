import { NavLink } from "react-router-dom";
import "./Navbar.css";

export default function Navbar() {
  return (
    <div className="navbar">
      <NavLink to="/" className="logo" style={{ textDecoration: "none" }}>
        💚 VitaCoach AI
      </NavLink>

      <div className="menu">
        <NavLink to="/trainings" className="nav-link">Trainings</NavLink>
        <NavLink to="/" end className="nav-link">AI Coach</NavLink>
        <NavLink to="/my-plan" className="nav-link">My Plan</NavLink>
      </div>
    </div>
  );
}