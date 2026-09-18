export const API_BASE = "http://127.0.0.1:9000";
export const AUTH_TOKEN_KEY = "vitacoach-auth-token";

export function getAuthToken() {
	return localStorage.getItem(AUTH_TOKEN_KEY) || "";
}

export function setAuthToken(token) {
	if (token) {
		localStorage.setItem(AUTH_TOKEN_KEY, token);
	} else {
		localStorage.removeItem(AUTH_TOKEN_KEY);
	}
}

async function parseResponse(response) {
	const contentType = response.headers.get("content-type") || "";
	if (contentType.includes("application/json")) {
		return response.json();
	}
	return response.text();
}

function formatApiError(data, response) {
	if (typeof data === "string") {
		return data;
	}

	if (Array.isArray(data?.detail)) {
		return data.detail
			.map((item) => {
				if (typeof item === "string") return item;
				const loc = Array.isArray(item?.loc) ? item.loc.join(".") : "request";
				const msg = item?.msg || "Invalid value";
				return `${loc}: ${msg}`;
			})
			.join("; ");
	}

	return data?.detail || data?.error || data?.message || response.statusText || "Request failed";
}

export async function apiRequest(path, { method = "GET", body, token = getAuthToken(), headers = {} } = {}) {
	const requestHeaders = { ...headers };
	if (body !== undefined) {
		requestHeaders["Content-Type"] = "application/json";
	}
	if (token) {
		requestHeaders.Authorization = `Bearer ${token}`;
	}

	const response = await fetch(`${API_BASE}${path}`, {
		method,
		headers: requestHeaders,
		body: body !== undefined ? JSON.stringify(body) : undefined,
	});

	const data = await parseResponse(response);
	if (!response.ok) {
		const message = formatApiError(data, response);
		throw new Error(message);
	}

	return data;
}

export function askQuestion(question) {
	// Auth is optional server-side — apiRequest attaches the token when present
	// (from localStorage via getAuthToken()) so signed-in users get their
	// preferences applied, and anonymous callers still work unauthenticated.
	return apiRequest("/ask", { method: "POST", body: { question } });
}

// Streaming variant of askQuestion. apiRequest can't be reused here — it does
// a single whole-body response.json()/.text() parse, not chunk-aware — so
// this is a dedicated sibling that reads the response body incrementally and
// parses Server-Sent-Events ("data: {...}\n\n") frames as they arrive.
// onDelta(text) fires per streamed chunk, onDone(payload) once with the
// final exercises/retrieval/personalized payload, onError(message) on any
// failure (network error, non-2xx, or an {error,...} SSE frame from the
// server) so the caller can fall back to the non-streaming askQuestion().
export async function askQuestionStream(question, { onDelta, onDone, onError } = {}) {
	const token = getAuthToken();
	const headers = { "Content-Type": "application/json" };
	if (token) headers.Authorization = `Bearer ${token}`;

	let response;
	try {
		response = await fetch(`${API_BASE}/ask/stream`, {
			method: "POST",
			headers,
			body: JSON.stringify({ question }),
		});
	} catch (err) {
		onError?.(err.message || "Network error");
		return;
	}

	if (!response.ok || !response.body) {
		onError?.(`Stream request failed (status ${response.status})`);
		return;
	}

	const reader = response.body.getReader();
	const decoder = new TextDecoder();
	let buffer = "";

	while (true) {
		const { value, done } = await reader.read();
		if (done) break;
		buffer += decoder.decode(value, { stream: true });

		let sepIndex;
		while ((sepIndex = buffer.indexOf("\n\n")) !== -1) {
			const frame = buffer.slice(0, sepIndex);
			buffer = buffer.slice(sepIndex + 2);
			if (!frame.startsWith("data: ")) continue;

			let payload;
			try {
				payload = JSON.parse(frame.slice("data: ".length));
			} catch {
				continue; // skip malformed frame rather than aborting the stream
			}

			if (payload.error) {
				onError?.(payload.error);
				if (payload.done) return;
			} else if (payload.done) {
				onDone?.(payload);
				return;
			} else if (typeof payload.delta === "string") {
				onDelta?.(payload.delta);
			}
		}
	}
}

export function registerUser(payload) {
	return apiRequest("/auth/register", { method: "POST", body: payload, token: "" });
}

export function loginUser(payload) {
	return apiRequest("/auth/login", { method: "POST", body: payload, token: "" });
}

export function fetchCurrentUser(token) {
	return apiRequest("/auth/me", { token });
}

export function logoutUser(token) {
	return apiRequest("/auth/logout", { method: "POST", token });
}

export function fetchUserPlan(token) {
	return apiRequest("/users/me/plan", { token });
}

export function saveUserPlan(token, items) {
	return apiRequest("/users/me/plan", { method: "PUT", token, body: { items } });
}

export function connectIntegration(token, serviceName) {
	return apiRequest(`/users/me/connections/${serviceName}`, { method: "POST", token });
}

export function connectGarminTest(token, payload = {}) {
	return apiRequest("/users/me/connections/garmin/test", {
		method: "POST",
		token,
		body: payload,
	});
}

export function fetchGarminDashboard(token) {
	return apiRequest("/users/me/garmin/dashboard", { token });
}

export function getCalendarEvents(token, daysAhead = 7) {
	return apiRequest(`/users/me/calendar/events?days_ahead=${daysAhead}`, { token });
}

export function getScheduleRecommendations(token, daysAhead = 7, language = "English", userLatitude = null, userLongitude = null) {
	const body = { daysAhead, language };
	if (userLatitude !== null && userLatitude !== undefined) body.userLatitude = userLatitude;
	if (userLongitude !== null && userLongitude !== undefined) body.userLongitude = userLongitude;

	return apiRequest("/users/me/schedule-recommendations", {
		method: "POST",
		token,
		body,
	});
}

export function fetchUserPreferences(token) {
	return apiRequest("/users/me/preferences", { token });
}

export function saveUserPreferences(token, preferences) {
	return apiRequest("/users/me/preferences", { method: "PUT", token, body: preferences });
}

export function analyzeUserPreferences(token) {
	return apiRequest("/users/me/preferences/analyze", { method: "POST", token });
}

export function createCalendarEvent(token, eventData) {
	return apiRequest("/users/me/calendar/events", {
		method: "POST",
		token,
		body: eventData,
	});
}
