/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useState } from "react";
import {
	connectIntegration,
	fetchCurrentUser,
	getAuthToken,
	loginUser,
	logoutUser,
	registerUser,
	setAuthToken,
} from "../lib/api.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
	const [token, setToken] = useState(() => getAuthToken());
	const [user, setUser] = useState(null);
	const [initializing, setInitializing] = useState(Boolean(getAuthToken()));

	useEffect(() => {
		let cancelled = false;

		if (!token) {
			setUser(null);
			setInitializing(false);
			return () => {
				cancelled = true;
			};
		}

		setInitializing(true);
		fetchCurrentUser(token)
			.then((data) => {
				if (cancelled) return;
				setUser(data.user || null);
				setAuthToken(token);
			})
			.catch(() => {
				if (cancelled) return;
				setToken("");
				setUser(null);
				setAuthToken("");
			})
			.finally(() => {
				if (!cancelled) {
					setInitializing(false);
				}
			});

		return () => {
			cancelled = true;
		};
	}, [token]);

	const completeAuth = (data) => {
		setAuthToken(data.token);
		setToken(data.token);
		setUser(data.user || null);
		setInitializing(false);
		return data;
	};

	const register = async (payload) => completeAuth(await registerUser(payload));
	const login = async (payload) => completeAuth(await loginUser(payload));

	const logout = async () => {
		try {
			if (token) {
				await logoutUser(token);
			}
		} catch {
			// best effort
		} finally {
			setAuthToken("");
			setToken("");
			setUser(null);
			setInitializing(false);
		}
	};

	const connectService = async (serviceName) => {
		if (!token) {
			throw new Error("Please log in first.");
		}

		const data = await connectIntegration(token, serviceName);
		if (serviceName === "google-calendar") {
			if (!data?.authUrl) {
				throw new Error("Google Calendar did not return a connect URL.");
			}
			window.location.assign(data.authUrl);
			return null;
		}

		setUser(data.user || null);
		return data.user || null;
	};

	const value = {
		user,
		token,
		initializing,
		isAuthenticated: Boolean(user && token),
		register,
		login,
		logout,
		connectService,
	};

	return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
	const context = useContext(AuthContext);
	if (!context) {
		throw new Error("useAuth must be used within AuthProvider");
	}

	return context;
}


