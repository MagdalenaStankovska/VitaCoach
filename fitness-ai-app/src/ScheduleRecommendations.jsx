import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "./auth/AuthContext.jsx";
import { getCalendarEvents, getScheduleRecommendations, createCalendarEvent } from "./lib/api.js";
import "./ScheduleRecommendations.css";

const WEEKDAY_LABELS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const WEEKDAY_LONG_LABELS = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
];

function pad(value) {
  return String(value).padStart(2, "0");
}

function startOfDay(date) {
  const next = new Date(date);
  next.setHours(0, 0, 0, 0);
  return next;
}

function addDays(date, amount) {
  const next = new Date(date);
  next.setDate(next.getDate() + amount);
  return next;
}

function toDateKey(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function parseDateValue(rawValue) {
  if (!rawValue) return null;

  if (typeof rawValue === "string" && /^\d{4}-\d{2}-\d{2}$/.test(rawValue)) {
    const [year, month, day] = rawValue.split("-").map(Number);
    return new Date(year, month - 1, day);
  }

  const parsed = new Date(rawValue);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function getEventStart(event) {
  return parseDateValue(
    event?.startTime ||
      event?.start?.dateTime ||
      event?.start?.date ||
      event?.dateTime ||
      event?.date ||
      event?.start,
  );
}

function getEventEnd(event) {
  return parseDateValue(
    event?.endTime || event?.end?.dateTime || event?.end?.date || event?.end,
  );
}

function getEventTitle(event) {
  return event?.title || event?.summary || event?.name || "Calendar event";
}

function getEventDescription(event) {
  return event?.description || event?.notes || event?.location || "";
}

function formatDayLabel(date) {
  return new Intl.DateTimeFormat(undefined, {
    weekday: "long",
    month: "short",
    day: "numeric",
  }).format(date);
}

function formatEventTime(startDate, endDate) {
  if (!startDate) return "All day";

  const timeFormatter = new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });

  if (!endDate) return timeFormatter.format(startDate);
  return `${timeFormatter.format(startDate)} - ${timeFormatter.format(endDate)}`;
}

function cleanSuggestionLine(line) {
  return String(line || "")
    .replace(/^[-*•]\s+/, "")
    .replace(/^\d+[.)]\s+/, "")
    .replace(/\*\*/g, "")
    .trim();
}

function normalizeWeekdayToken(token) {
  const short = String(token || "")
    .slice(0, 3)
    .toLowerCase();
  const map = {
    sun: "sunday",
    mon: "monday",
    tue: "tuesday",
    wed: "wednesday",
    thu: "thursday",
    fri: "friday",
    sat: "saturday",
  };
  return map[short] || "";
}

function parseDayHeading(line) {
  const regex =
    /^(?:[-*]\s*)?(?:#{1,6}\s*)?(?:\*\*)?\s*(Sunday|Sun|Monday|Mon|Tuesday|Tue|Wednesday|Wed|Thursday|Thu|Friday|Fri|Saturday|Sat)\b[\s,.-]*(?:\(?\s*)?([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?\s*\)?\s*[:\-–]?(?:\*\*)?\s*(.*)$/i;
  const match = String(line || "")
    .trim()
    .match(regex);
  if (!match) return null;

  return {
    weekday: normalizeWeekdayToken(match[1]),
    month: match[2].toLowerCase().replace(/\.$/, ""),
    day: Number(match[3]),
    rest: cleanSuggestionLine(match[4]),
  };
}

function extractFullDaySection(planText, selectedDate) {
  if (!selectedDate || typeof planText !== "string" || !planText.trim()) {
    return [];
  }

  const weekdayLong = WEEKDAY_LONG_LABELS[selectedDate.getDay()];
  const year = selectedDate.getFullYear();
  const month = String(selectedDate.getMonth() + 1).padStart(2, "0");
  const day = String(selectedDate.getDate()).padStart(2, "0");

  const dayHeadingRegex = new RegExp(
    `^${weekdayLong}\\s*\\(${year}-${month}-${day}\\)\\s*:?\\s*(.*?)$`,
    "im",
  );

  const lines = planText.replace(/\r/g, "").split("\n");
  let startIdx = -1;

  for (let i = 0; i < lines.length; i += 1) {
    if (dayHeadingRegex.test(lines[i])) {
      startIdx = i;
      break;
    }
  }

  if (startIdx === -1) return [];

  const result = [];
  for (let i = startIdx + 1; i < lines.length; i += 1) {
    const line = lines[i].trim();
    if (!line) break;
    if (/^[A-Z][a-z]+\s*\(\d{4}-\d{2}-\d{2}\)/.test(line)) break;
    result.push(cleanSuggestionLine(line));
  }

  return result.filter(Boolean);
}

function extractDaySpecificSuggestions(planText, selectedDate) {
  if (!selectedDate || typeof planText !== "string" || !planText.trim()) {
    return [];
  }

  const targetWeekday =
    WEEKDAY_LONG_LABELS[selectedDate.getDay()].toLowerCase();
  const targetDay = selectedDate.getDate();
  const monthLong = new Intl.DateTimeFormat("en-US", { month: "long" })
    .format(selectedDate)
    .toLowerCase();
  const monthShort = new Intl.DateTimeFormat("en-US", { month: "short" })
    .format(selectedDate)
    .toLowerCase()
    .replace(/\.$/, "");
  const allowedMonths = new Set([monthLong, monthShort]);

  const sections = [];
  let current = null;

  planText
    .replace(/\r/g, "")
    .split("\n")
    .forEach((rawLine) => {
      const line = rawLine.trim();
      if (!line) return;

      const heading = parseDayHeading(line);
      if (heading) {
        if (current) sections.push(current);
        current = {
          weekday: heading.weekday,
          month: heading.month,
          day: heading.day,
          items: heading.rest ? [heading.rest] : [],
        };
        return;
      }

      if (!current) return;

      const cleaned = cleanSuggestionLine(line);
      if (!cleaned) return;
      if (/^[A-Z][A-Z\s/&-]{4,}:$/.test(cleaned)) return;
      current.items.push(cleaned);
    });

  if (current) sections.push(current);

  const daySections = sections.filter(
    (section) =>
      section.weekday === targetWeekday &&
      section.day === targetDay &&
      allowedMonths.has(section.month),
  );

  return daySections
    .flatMap((section) => section.items)
    .map(cleanSuggestionLine)
    .filter(Boolean);
}

function formatDetailedAnalysisBlocks(planText) {
  if (typeof planText !== "string" || !planText.trim()) {
    return [];
  }

  return planText
    .replace(/\r/g, "")
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean)
    .map((block) => {
      const lines = block
        .split("\n")
        .map((line) => cleanSuggestionLine(line))
        .filter(Boolean);

      if (lines.length === 0) {
        return null;
      }

      const first = lines[0];
      const isTitle =
        /[:：]$/.test(first) ||
        /^(?:[^\w\s]{1,3}\s*)?[A-Z][A-Z\s/&-]{3,}:$/.test(first);
      return {
        title: isTitle ? first : "",
        body: isTitle ? lines.slice(1) : lines,
      };
    })
    .filter(Boolean);
}

function chunkDays(items, size = 7) {
  const chunks = [];
  for (let index = 0; index < items.length; index += size) {
    const week = items.slice(index, index + size);
    while (week.length < size) {
      week.push(null);
    }
    chunks.push(week);
  }
  return chunks;
}

function parseEventFromSuggestion(suggestion, selectedDate) {
  /**
   * Parse a suggestion text to extract event details.
   * Examples:
   *   "Workout: 30-45 minutes (use gym)" -> title: "Workout", time: "09:00", duration: 30-45
   *   "Breakfast: 6:30 AM" -> title: "Breakfast", time: "06:30"
   *   "Lunch: 12:00 PM" -> title: "Lunch", time: "12:00"
   */
  if (!suggestion || !selectedDate) return null;

  const text = String(suggestion).trim();
  
  // Try to extract time from text (HH:MM format or AM/PM format)
  const timeMatch = text.match(/(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)?/);
  let hours = 9; // default
  let minutes = 0;
  
  if (timeMatch) {
    hours = parseInt(timeMatch[1], 10);
    minutes = parseInt(timeMatch[2], 10);
    
    // Convert 12-hour to 24-hour if AM/PM specified
    if (timeMatch[3]) {
      const isPM = timeMatch[3].toUpperCase() === "PM";
      if (isPM && hours !== 12) hours += 12;
      if (!isPM && hours === 12) hours = 0;
    }
  }
  
  // Extract title (first part before colon or first few words)
  let title = text.split(/[:,]/)[0].trim();
  if (title.length > 50) title = title.substring(0, 50);
  
  // Create ISO datetime strings
  const startDate = new Date(selectedDate);
  startDate.setHours(hours, minutes, 0, 0);
  const startIso = startDate.toISOString();
  
  const endDate = new Date(startDate);
  endDate.setHours(hours + 1, minutes, 0, 0); // Default 1 hour duration
  const endIso = endDate.toISOString();
  
  return {
    title: title || "AI Recommendation",
    description: text,
    startTime: startIso,
    endTime: endIso,
  };
}

export default function ScheduleRecommendations() {
  const navigate = useNavigate();
  const { user, token, isAuthenticated } = useAuth();
  const [loading, setLoading] = useState(false);
  const [events, setEvents] = useState([]);
  const [recommendations, setRecommendations] = useState(null);
  const [error, setError] = useState("");
  const [daysAhead, setDaysAhead] = useState(7);
  const [selectedDayKey, setSelectedDayKey] = useState("");
  const [suggestionDecisions, setSuggestionDecisions] = useState({});
  const [creatingEvent, setCreatingEvent] = useState({}); // Track which events are being created
  const [eventCreateMessage, setEventCreateMessage] = useState(""); // Feedback message

  const nearestRestaurants =
    recommendations?.nearestRestaurants ||
    (recommendations?.nearestRestaurant
      ? [recommendations.nearestRestaurant]
      : []);
  const nearestGyms =
    recommendations?.nearestGyms ||
    recommendations?.nearestTrainingSpots ||
    (recommendations?.nearestGym ? [recommendations.nearestGym] : []);
  const detailedAnalysisBlocks = useMemo(
    () => formatDetailedAnalysisBlocks(recommendations?.recommendations),
    [recommendations?.recommendations],
  );

  const calendarDays = useMemo(() => {
    const today = startOfDay(new Date());
    const groupedEvents = new Map();

    events.forEach((event) => {
      const startDate = getEventStart(event);
      if (!startDate) return;

      const key = toDateKey(startDate);
      if (!groupedEvents.has(key)) {
        groupedEvents.set(key, []);
      }

      groupedEvents.get(key).push({
        ...event,
        __startDate: startDate,
        __endDate: getEventEnd(event),
      });
    });

    const days = [];
    for (let offset = 0; offset < daysAhead; offset += 1) {
      const date = addDays(today, offset);
      const key = toDateKey(date);
      const dayEvents = (groupedEvents.get(key) || []).sort((left, right) => {
        const leftTime = left.__startDate?.getTime?.() || 0;
        const rightTime = right.__startDate?.getTime?.() || 0;
        return leftTime - rightTime;
      });

      days.push({
        key,
        date,
        label: formatDayLabel(date),
        weekdayShort: WEEKDAY_LABELS[date.getDay()],
        weekdayLong: WEEKDAY_LONG_LABELS[date.getDay()],
        isToday: key === toDateKey(today),
        events: dayEvents,
      });
    }

    return days;
  }, [events, daysAhead]);

  const calendarWeeks = useMemo(
    () => chunkDays(calendarDays, 7),
    [calendarDays],
  );
  const selectedDay = useMemo(
    () => calendarDays.find((day) => day.key === selectedDayKey) || null,
    [calendarDays, selectedDayKey],
  );
  const selectedDaySuggestions = useMemo(() => {
    if (!selectedDay || !recommendations) return [];

    const daySpecific = extractDaySpecificSuggestions(
      recommendations.recommendations,
      selectedDay.date,
    );
    if (daySpecific.length > 0) return daySpecific;

        return extractFullDaySection(
      recommendations.recommendations,
      selectedDay.date,
    );
  }, [selectedDay, recommendations]);

  const loadScheduleData = useCallback(async () => {
    if (!isAuthenticated || !token) return;

    setLoading(true);
    setError("");

    try {
      // Get user's location
      let userLatitude = null;
      let userLongitude = null;

      if (navigator.geolocation) {
        try {
          const position = await new Promise((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(resolve, reject, {
              enableHighAccuracy: true,
              timeout: 5000,
              maximumAge: 0,
            });
          });
          userLatitude = position.coords.latitude;
          userLongitude = position.coords.longitude;
          console.log("📍 User location:", userLatitude, userLongitude);
        } catch (err) {
          console.log("⚠️ Location access denied or unavailable:", err.message);
        }
      }

      // Fetch calendar events (best-effort only, recommendations should still load).
      let eventsRes = { events: [], connected: false };
      try {
        eventsRes = await getCalendarEvents(token, daysAhead);
      } catch (calendarErr) {
        console.warn("Calendar fetch failed, continuing:", calendarErr);
      }
      setEvents(eventsRes.events || []);

      // Always fetch recommendations with location so nearby Korpa + gyms are returned.
      const recsRes = await getScheduleRecommendations(
        token,
        daysAhead,
        "English",
        userLatitude,
        userLongitude,
      );
      setRecommendations(recsRes);

      if (!eventsRes.connected) {
        setError(
          "Google Calendar is not connected or unavailable right now. Nearby Korpa and gyms are still shown.",
        );
      }
    } catch (err) {
      console.error("Error loading schedule data:", err);
      setError(err.message || "Failed to load calendar data");
    } finally {
      setLoading(false);
    }
  }, [daysAhead, isAuthenticated, token]);

  useEffect(() => {
    if (isAuthenticated) {
      loadScheduleData();
    }
  }, [isAuthenticated, loadScheduleData]);

  useEffect(() => {
    const closeOnEscape = (event) => {
      if (event.key === "Escape") {
        setSelectedDayKey("");
      }
    };

    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, []);

  const handleRefresh = () => {
    loadScheduleData();
  };

  const handleOpenDay = (dayKey) => {
    setSelectedDayKey(dayKey);
  };

  const handleCloseModal = () => {
    setSelectedDayKey("");
  };

  const updateSuggestionDecision = (dayKey, suggestionIndex, decision) => {
    setSuggestionDecisions((previous) => {
      const dayDecisions = { ...(previous[dayKey] || {}) };
      const currentDecision = dayDecisions[suggestionIndex] || "";
      const nextDecision = currentDecision === decision ? "" : decision;

      if (nextDecision) {
        dayDecisions[suggestionIndex] = nextDecision;
      } else {
        delete dayDecisions[suggestionIndex];
      }

      const nextState = { ...previous };
      if (Object.keys(dayDecisions).length > 0) {
        nextState[dayKey] = dayDecisions;
      } else {
        delete nextState[dayKey];
      }

      return nextState;
    });
  };

  const handleAddEventToCalendar = async (suggestion, suggestionIndex, dayKey) => {
    if (!selectedDay) return;
    
    const eventKey = `${dayKey}-${suggestionIndex}`;
    setCreatingEvent((prev) => ({ ...prev, [eventKey]: true }));
    setEventCreateMessage("");
    
    try {
      const eventData = parseEventFromSuggestion(suggestion, selectedDay.date);
      if (!eventData) {
        throw new Error("Could not parse event details from suggestion");
      }
      
      const result = await createCalendarEvent(token, eventData);
      
      if (result.success) {
        setEventCreateMessage(`✅ Event added to calendar: "${result.title}"`);
        // Clear message after 3 seconds
        setTimeout(() => setEventCreateMessage(""), 3000);
      } else {
        throw new Error(result.error || "Failed to create event");
      }
    } catch (err) {
      console.error("Error adding event:", err);
      setEventCreateMessage(`❌ Failed to add event: ${err.message}`);
      setTimeout(() => setEventCreateMessage(""), 3000);
    } finally {
      setCreatingEvent((prev) => {
        const next = { ...prev };
        delete next[eventKey];
        return next;
      });
    }
  };

  if (!isAuthenticated) {
    return (
      <div className="schedule-container">
        <div className="schedule-card">
          <p className="schedule-message">
            Please log in to use schedule recommendations.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="schedule-container">
      <div className="schedule-header">
        <h2>📅 Google Calendar Day View</h2>
        <div className="schedule-header-buttons">
          <button
            onClick={handleRefresh}
            disabled={loading}
            className="refresh-btn"
          >
            {loading ? "Analyzing..." : "🔄 Refresh Calendar"}
          </button>
          <button
            onClick={() => navigate("/")}
            className="home-btn"
            title="Go to Home"
          >
            🏠 Home
          </button>
        </div>
      </div>

      {error && (
        <div className="schedule-error">
          <span>⚠️ {error}</span>
        </div>
      )}

      {!user?.googleCalendarConnected && (
        <div className="schedule-card">
          <h3>🔗 Google Calendar Not Connected</h3>
          <p>
            You can still see nearby Korpa restaurants and gyms. Connect Google
            Calendar any time for event-based suggestions.
          </p>
        </div>
      )}

      {loading && (
        <div className="schedule-loading">
          <div className="spinner"></div>
          <p>Loading your calendar and preparing day suggestions...</p>
        </div>
      )}

      <div className="schedule-calendar-shell">
        <div className="schedule-calendar-intro">
          <div>
            <h3>📆 Upcoming days</h3>
            <p>
              Click any day to see your Google Calendar obligations and decide
              which AI suggestions fit best.
            </p>
          </div>
          <div className="schedule-calendar-meta">
            <span className="schedule-calendar-pill">
              {calendarDays.length} day view
            </span>
            <span className="schedule-calendar-pill">
              {events.length} events loaded
            </span>
          </div>
        </div>

        <div className="calendar-board">
          <div className="calendar-weekdays">
            {WEEKDAY_LABELS.map((day) => (
              <div key={day} className="calendar-weekday">
                {day}
              </div>
            ))}
          </div>

          <div className="calendar-weeks">
            {calendarWeeks.map((week, weekIndex) => (
              <div key={`week-${weekIndex}`} className="calendar-week">
                {week.map((day) => {
                  if (!day) {
                    return (
                      <div
                        key={`empty-${weekIndex}`}
                        className="calendar-day calendar-day-empty"
                        aria-hidden="true"
                      />
                    );
                  }

                  const isSelected = selectedDayKey === day.key;
                  const previewEvents = day.events.slice(0, 3);

                  return (
                    <button
                      key={day.key}
                      type="button"
                      className={`calendar-day${day.isToday ? " is-today" : ""}${isSelected ? " is-selected" : ""}`}
                      onClick={() => handleOpenDay(day.key)}
                    >
                      <div className="calendar-day-header">
                        <span className="calendar-day-weekday">
                          {day.weekdayShort}
                        </span>
                        <span className="calendar-day-number">
                          {day.date.getDate()}
                        </span>
                      </div>

                      <div className="calendar-day-label">
                        {day.weekdayLong}
                      </div>

                      <div className="calendar-event-preview">
                        {previewEvents.length > 0 ? (
                          previewEvents.map((event, eventIndex) => (
                            <div
                              key={`${day.key}-${eventIndex}`}
                              className="calendar-event-preview-item"
                            >
                              <span className="calendar-event-preview-time">
                                {formatEventTime(
                                  event.__startDate,
                                  event.__endDate,
                                )}
                              </span>
                              <span className="calendar-event-preview-title">
                                {getEventTitle(event)}
                              </span>
                            </div>
                          ))
                        ) : (
                          <div className="calendar-event-empty">
                            No obligations yet
                          </div>
                        )}
                        {day.events.length > 3 && (
                          <div className="calendar-event-more">
                            +{day.events.length - 3} more
                          </div>
                        )}
                      </div>

                      <div className="calendar-day-footer">
                        {day.events.length > 0
                          ? `${day.events.length} obligation${day.events.length === 1 ? "" : "s"}`
                          : "Open day view"}
                      </div>
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </div>

      {recommendations && (
        <div className="schedule-recommendations long-card">
          <h3>🤖 Full Plan Panel</h3>
          <p className="schedule-help-text">
            Open a day in the calendar to accept or reject the AI suggestions.
            The full written plan stays here.
          </p>

          {nearestRestaurants.length > 0 && (
            <div className="nearest-restaurant">
              <h4>📍 Top 3 Nearest Restaurants</h4>
              <div className="restaurant-list">
                {nearestRestaurants.slice(0, 3).map((restaurant, idx) => (
                  <div
                    key={`${restaurant.name}-${idx}`}
                    className="restaurant-card"
                  >
                    <div className="restaurant-info">
                      <p className="restaurant-rank">#{idx + 1}</p>
                      <p className="restaurant-name">{restaurant.name}</p>
                      <p className="restaurant-distance">
                        📏 {restaurant.distance_km} km away
                      </p>
                      <p className="restaurant-address">
                        📍 {restaurant.address}
                      </p>
                      <a
                        href={restaurant.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="restaurant-link"
                      >
                        🔗 Order on Korpa
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {nearestGyms.length > 0 && (
            <div className="nearest-gyms">
              <h4>🏋️ Top 3 Nearest Gyms & Training Spots</h4>
              <div className="gym-list">
                {nearestGyms.slice(0, 3).map((gym, idx) => (
                  <div key={`${gym.name}-${idx}`} className="gym-card">
                    <div className="gym-info">
                      <p className="restaurant-rank">#{idx + 1}</p>
                      <p className="restaurant-name">{gym.name}</p>
                      <p className="restaurant-distance">
                        📏 {gym.distance_km} km away
                      </p>
                      <p className="restaurant-address">📍 {gym.address}</p>
                      {gym.url && (
                        <a
                          href={gym.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="restaurant-link"
                        >
                          🔗 Open location
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/*{recommendations.meals && recommendations.meals.length > 0 && (*/}
          {/*  <div className="korpa-meals">*/}
          {/*    <h4>🍽️ Quick Meal Options from Korpa</h4>*/}
          {/*    <div className="meals-grid">*/}
          {/*      {recommendations.meals.map((meal, idx) => (*/}
          {/*        <div key={idx} className="meal-card">*/}
          {/*          <p className="meal-name">{meal.name}</p>*/}
          {/*        </div>*/}
          {/*      ))}*/}
          {/*    </div>*/}
          {/*  </div>*/}
          {/*)}*/}

          <div className="recommendations-text answer-block">
            <h4>📝 Detailed Analysis</h4>
            <div className="recommendation-content">
              {detailedAnalysisBlocks.length > 0
                ? detailedAnalysisBlocks.map((block, index) => (
                    <article
                      key={`analysis-${index}`}
                      className="analysis-block answer-block"
                    >
                      {block.title && <h5>{block.title}</h5>}
                      <div className="analysis-lines">
                        {block.body.map((line, lineIndex) => (
                          <p key={`analysis-${index}-${lineIndex}`}>{line}</p>
                        ))}
                      </div>
                    </article>
                  ))
                : recommendations.recommendations}
            </div>
          </div>
        </div>
      )}

      {!loading && !recommendations && !error && (
        <div className="schedule-card">
          <p className="schedule-message">
            Click "Refresh Calendar" to load personalized recommendations based
            on your Google Calendar.
          </p>
        </div>
      )}

      <div className="schedule-settings">
        <label>
          Days to analyze:
          <input
            type="number"
            min="1"
            max="30"
            value={daysAhead}
            onChange={(e) =>
              setDaysAhead(
                Math.max(1, Math.min(30, parseInt(e.target.value) || 7)),
              )
            }
            disabled={loading}
          />
        </label>
        <button
          onClick={handleRefresh}
          disabled={loading}
          className="analyze-btn"
        >
          {loading ? "Analyzing..." : "Analyze"}
        </button>
      </div>

      {selectedDay && (
        <div
          className="calendar-modal-backdrop"
          onClick={handleCloseModal}
          role="presentation"
        >
          <div
            className="calendar-modal"
            onClick={(event) => event.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label={`Calendar details for ${selectedDay.label}`}
          >
            <div className="calendar-modal-header">
              <div>
                <p className="calendar-modal-kicker">Day view</p>
                <h3>{selectedDay.label}</h3>
                <p className="calendar-modal-subtitle">
                  {selectedDay.events.length > 0
                    ? `${selectedDay.events.length} Google Calendar obligation${selectedDay.events.length === 1 ? "" : "s"}`
                    : "No Google Calendar obligations yet for this day"}
                </p>
              </div>
              <button
                type="button"
                className="calendar-modal-close"
                onClick={handleCloseModal}
                aria-label="Close day details"
              >
                ×
              </button>
            </div>

            <div className="calendar-modal-content">
              <section className="calendar-modal-panel">
                <div className="calendar-panel-header">
                  <h4>Google Calendar obligations</h4>
                  <span className="calendar-panel-pill">
                    {selectedDay.weekdayLong}
                  </span>
                </div>

                <div className="calendar-event-list">
                  {selectedDay.events.length > 0 ? (
                    selectedDay.events.map((event, index) => (
                      <article
                        key={`${selectedDay.key}-${index}`}
                        className="calendar-event-card"
                      >
                        <div className="calendar-event-time">
                          {formatEventTime(event.__startDate, event.__endDate)}
                        </div>
                        <div className="calendar-event-details">
                          <h5>{getEventTitle(event)}</h5>
                          {getEventDescription(event) && (
                            <p>{getEventDescription(event)}</p>
                          )}
                        </div>
                      </article>
                    ))
                  ) : (
                    <div className="calendar-empty-panel">
                      <p>No obligations were loaded for this day.</p>
                      <p className="small-text">
                        Add events to Google Calendar and refresh to see them
                        here.
                      </p>
                    </div>
                  )}
                </div>
              </section>

              <section className="calendar-modal-panel">
                <div className="calendar-panel-header">
                  <h4>AI suggestions</h4>
                  <span className="calendar-panel-pill">Accept / reject</span>
                </div>

                <div className="ai-suggestion-list">
                   {selectedDaySuggestions.length > 0 ? (
                     selectedDaySuggestions.map((suggestion, index) => {
                       const decision =
                         suggestionDecisions[selectedDay.key]?.[index] || "";
                       return (
                         <article
                           key={`${selectedDay.key}-suggestion-${index}`}
                           className={`ai-suggestion-card${decision ? ` is-${decision}` : ""}`}
                         >
                           <p>{suggestion}</p>
                           <div className="ai-suggestion-actions">
                             <button
                               type="button"
                               className={`decision-btn accept${decision === "accepted" ? " is-active" : ""}`}
                               onClick={() =>
                                 updateSuggestionDecision(
                                   selectedDay.key,
                                   index,
                                   "accepted",
                                 )
                               }
                             >
                               {decision === "accepted" ? "Accepted" : "Accept"}
                             </button>
                             <button
                               type="button"
                               className={`decision-btn reject${decision === "rejected" ? " is-active" : ""}`}
                               onClick={() =>
                                 updateSuggestionDecision(
                                   selectedDay.key,
                                   index,
                                   "rejected",
                                 )
                               }
                             >
                               {decision === "rejected" ? "Rejected" : "Reject"}
                             </button>
                             {decision === "accepted" && (
                               <button
                                 type="button"
                                 className="decision-btn add-to-calendar"
                                 disabled={creatingEvent[`${selectedDay.key}-${index}`]}
                                 onClick={() =>
                                   handleAddEventToCalendar(
                                     suggestion,
                                     index,
                                     selectedDay.key,
                                   )
                                 }
                               >
                                 {creatingEvent[`${selectedDay.key}-${index}`]
                                   ? "Adding..."
                                   : "📅 Add to Calendar"}
                               </button>
                             )}
                           </div>
                           {decision && (
                             <span className={`decision-pill ${decision}`}>
                               {decision === "accepted"
                                 ? "Approved for this day"
                                 : "Rejected for now"}
                             </span>
                           )}
                         </article>
                       );
                     })
                   ) : (
                     <div className="calendar-empty-panel">
                       <p>No suggestions detected for this day yet.</p>
                       <p className="small-text">
                         Try Refresh Calendar if your plan was updated.
                       </p>
                     </div>
                   )}
                 </div>
              </section>
            </div>

            <div className="calendar-modal-footer">
               {eventCreateMessage && (
                 <div className="event-create-message">
                   {eventCreateMessage}
                 </div>
               )}
               <button
                 type="button"
                 className="home-btn"
                 onClick={handleCloseModal}
               >
                 Close day view
               </button>
             </div>
          </div>
        </div>
      )}
    </div>
  );
}
