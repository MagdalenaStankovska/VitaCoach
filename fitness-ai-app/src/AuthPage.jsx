import { useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import Navbar from "./Navbar.jsx";
import { useAuth } from "./auth/AuthContext.jsx";
import "./Auth.css";

export default function AuthPage({ mode = "login" }) {
	const navigate = useNavigate();
	const { isAuthenticated, initializing, login, register } = useAuth();
	const [formMode, setFormMode] = useState(mode);
	const [error, setError] = useState("");
	const [loading, setLoading] = useState(false);
	const [formData, setFormData] = useState({
		name: "",
		email: "",
		password: "",
	});

	useEffect(() => {
		setFormMode(mode);
		setError("");
	}, [mode]);

	useEffect(() => {
		if (isAuthenticated && !initializing) {
			navigate("/", { replace: true });
		}
	}, [isAuthenticated, initializing, navigate]);

	const handleChange = (event) => {
		const { name, value } = event.target;
		setFormData((current) => ({ ...current, [name]: value }));
	};

	const handleSubmit = async (event) => {
		event.preventDefault();
		setError("");
		setLoading(true);

		try {
			if (formMode === "register") {
				await register(formData);
			} else {
				await login(formData);
			}
			navigate("/", { replace: true });
		} catch (submitError) {
			setError(submitError.message || "Something went wrong.");
		} finally {
			setLoading(false);
		}
	};

	return (
		<div className="app auth-page">
			<Navbar />

			<div className="auth-shell">
				<section className="hero auth-hero">
					<span className="hero-badge">✦ Account access</span>
					<h1>{formMode === "register" ? "Create your account" : "Welcome back"}</h1>
					<p>
						Log in to save your exercises per user and unlock optional Google Calendar and Garmin buttons in the header.
					</p>
					<div className="auth-points">
						<div>
							<strong>Personalized plan</strong>
							<span>Your saved exercises belong to your account only.</span>
						</div>
						<div>
							<strong>Optional integrations</strong>
							<span>Connect Google Calendar or Garmin later from the header.</span>
						</div>
					</div>
				</section>

				<section className="card auth-card">
					<div className="auth-tabs">
						<NavLink to="/login" className={({ isActive }) => `auth-tab ${isActive ? "active" : ""}`}>
							Log in
						</NavLink>
						<NavLink to="/register" className={({ isActive }) => `auth-tab ${isActive ? "active" : ""}`}>
							Register
						</NavLink>
					</div>

					<form className="auth-form" onSubmit={handleSubmit}>
						{formMode === "register" && (
							<label>
								Full name
								<input type="text" name="name" value={formData.name} onChange={handleChange} placeholder="Your name" autoComplete="name" />
							</label>
						)}

						<label>
							Email
							<input type="email" name="email" value={formData.email} onChange={handleChange} placeholder="you@example.com" autoComplete="email" />
						</label>

						<label>
							Password
							<input
								type="password"
								name="password"
								value={formData.password}
								onChange={handleChange}
								placeholder="Enter your password"
								autoComplete={formMode === "register" ? "new-password" : "current-password"}
							/>
						</label>

						{error && <div className="auth-error">{error}</div>}

						<button type="submit" className="auth-submit" disabled={loading}>
							{loading ? "Please wait..." : formMode === "register" ? "Create account" : "Log in"}
						</button>
					</form>
				</section>
			</div>
		</div>
	);
}

