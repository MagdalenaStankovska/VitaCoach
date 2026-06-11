import { useEffect, useMemo, useState } from "react";
import { NavLink } from "react-router-dom";
import Navbar from "./Navbar.jsx";
import { clearPlanMedia, deletePlanMedia, getManyPlanMedia, setPlanMedia } from "./lib/planMediaStore.js";
import { fetchUserPlan, saveUserPlan } from "./lib/api.js";
import { useAuth } from "./auth/AuthContext.jsx";

const API_BASE = "http://127.0.0.1:9000";

// Keeps media alive across in-app navigation without bloating localStorage.
const PLAN_MEDIA_CACHE = new Map();

function exerciseKey(ex) {
    return ex?.raw || ex?.name || "";
}

function stripPlanMedia(items) {
    return (items || []).map((item) => {
        const copy = { ...item };
        delete copy.images;
        return copy;
    });
}

function favoritesStorageKey(userId) {
    return `favoriteExercises:${userId || "guest"}`;
}

export default function MyPlan() {
    const { isAuthenticated, token, user, initializing } = useAuth();
    const [plan, setPlan] = useState([]);
    const [favorites, setFavorites] = useState([]);
    const [showFavoritesOnly, setShowFavoritesOnly] = useState(false);
    const [selectedExercise, setSelectedExercise] = useState(null);
    const [showVideo, setShowVideo] = useState(false);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
        let cancelled = false;

        if (!isAuthenticated || !token) {
            setPlan([]);
            setFavorites([]);
            setLoading(false);
            setError("");
            return () => { cancelled = true; };
        }

        (async () => {
            setLoading(true);
            setError("");

            let storedPlan = [];
            try {
                const response = await fetchUserPlan(token);
                storedPlan = Array.isArray(response.items) ? response.items : [];
            } catch (loadError) {
                if (!cancelled) {
                    setError(loadError.message || "Could not load your saved plan.");
                    setLoading(false);
                }
                return;
            }

            const keys = storedPlan.map((ex) => exerciseKey(ex)).filter(Boolean);
            const persisted = await getManyPlanMedia(keys);

            const withCache = storedPlan.map((ex) => {
                const key = exerciseKey(ex);
                const persistedMedia = persisted[key];
                const cached = PLAN_MEDIA_CACHE.get(key) || persistedMedia;
                if (persistedMedia) {
                    PLAN_MEDIA_CACHE.set(key, persistedMedia);
                }
                return cached
                    ? {
                        ...ex,
                        images: ex.images?.length ? ex.images : (cached.images || []),
                        video: ex.video || cached.video,
                        label: ex.label || cached.label,
                    }
                    : ex;
            });

            if (cancelled) return;
            setPlan(withCache);

            try {
                const storedFavorites = JSON.parse(localStorage.getItem(favoritesStorageKey(user?.id)) || "[]");
                setFavorites(Array.isArray(storedFavorites) ? storedFavorites : []);
            } catch {
                setFavorites([]);
            }

            // Recover missing image/video for saved items (images were intentionally stripped for quota safety).
            const needsRecovery = withCache.some((ex) => {
                const hasImage = Array.isArray(ex.images) && ex.images.some(Boolean);
                return !hasImage || !ex.video;
            });

            if (!needsRecovery) {
                setLoading(false);
                return;
            }

            try {
                const recovered = await Promise.all(withCache.map(async (ex) => {
                    const hasImage = Array.isArray(ex.images) && ex.images.some(Boolean);
                    const hasVideo = Boolean(ex.video);
                    if (hasImage && hasVideo) return ex;

                    const text = ex.raw || ex.name || "";
                    if (!text) return ex;

                    try {
                        const res = await fetch(`${API_BASE}/exercise-assets?text=${encodeURIComponent(text)}`);
                        const media = await res.json();
                        const merged = {
                            ...ex,
                            label: ex.label || media.label || ex.label,
                            images: hasImage ? ex.images : (media.image ? [media.image] : []),
                            video: hasVideo ? ex.video : media.video,
                        };
                        const mediaPayload = {
                            label: merged.label,
                            images: merged.images,
                            video: merged.video,
                        };
                        PLAN_MEDIA_CACHE.set(exerciseKey(merged), mediaPayload);
                        await setPlanMedia(exerciseKey(merged), mediaPayload);
                        return merged;
                    } catch {
                        return ex;
                    }
                }));

                if (cancelled) return;
                setPlan(recovered);
            } catch (recoveryError) {
                if (!cancelled) {
                    setError(recoveryError.message || "Could not refresh saved exercise media.");
                }
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        })();

        return () => { cancelled = true; };
    }, [isAuthenticated, token, user?.id]);

    const getExerciseKey = (exercise) => exercise.raw || exercise.name;

    const removeExercise = async (index) => {
        const updated = [...plan];
        const removed = updated[index];
        updated.splice(index, 1);

        try {
            await saveUserPlan(token, stripPlanMedia(updated));
            setPlan(updated);
        } catch (saveError) {
            setError(saveError.message || "Could not update your plan.");
            return;
        }

        if (removed) {
            const removedKey = getExerciseKey(removed);
            PLAN_MEDIA_CACHE.delete(removedKey);
            deletePlanMedia(removedKey);
            const updatedFavorites = favorites.filter((key) => key !== removedKey);
            setFavorites(updatedFavorites);
            localStorage.setItem(favoritesStorageKey(user?.id), JSON.stringify(updatedFavorites));
        }
    };

    const clearAll = async () => {
        try {
            await saveUserPlan(token, []);
        } catch (saveError) {
            setError(saveError.message || "Could not clear your plan.");
            return;
        }

        PLAN_MEDIA_CACHE.clear();
        clearPlanMedia();
        setPlan([]);
        setFavorites([]);
        setShowFavoritesOnly(false);
        localStorage.removeItem(favoritesStorageKey(user?.id));
    };

    const toggleFavorite = (exercise) => {
        const key = getExerciseKey(exercise);
        const updatedFavorites = favorites.includes(key)
            ? favorites.filter((item) => item !== key)
            : [...favorites, key];

        setFavorites(updatedFavorites);
        localStorage.setItem(favoritesStorageKey(user?.id), JSON.stringify(updatedFavorites));
    };

    const visiblePlan = useMemo(() => {
        if (!showFavoritesOnly) {
            return plan;
        }

        return plan.filter((exercise) => favorites.includes(getExerciseKey(exercise)));
    }, [plan, favorites, showFavoritesOnly]);

    const openExerciseModal = (exercise) => {
        setSelectedExercise(exercise);
        setShowVideo(false);
    };

    const closeExerciseModal = () => {
        setSelectedExercise(null);
        setShowVideo(false);
    };

    if (!initializing && !isAuthenticated) {
        return (
            <div className="app">
                <Navbar />

                <div className="hero">
                    <span className="hero-badge">✦ Personal collection</span>
                    <h1>💚 My Training Plan</h1>
                    <p>Log in to see the exercises saved in your private plan.</p>
                </div>

                <div className="card" style={{ textAlign: "center", padding: "48px 32px", maxWidth: "480px" }}>
                    <div style={{ fontSize: "52px", marginBottom: "16px" }}>🔐</div>
                    <h3 style={{ color: "#bbf7d0", marginBottom: "12px", fontSize: "20px" }}>Login required</h3>
                    <p style={{ color: "#94a3b8", lineHeight: "1.7", marginBottom: "24px" }}>
                        Each user has their own saved exercises and plan history.
                    </p>
                    <div style={{ display: "flex", gap: "12px", justifyContent: "center", flexWrap: "wrap" }}>
                        <NavLink
                            to="/login"
                            className="save-btn"
                            style={{ textDecoration: "none", display: "inline-flex", alignItems: "center" }}
                        >
                            Log in
                        </NavLink>
                        <NavLink
                            to="/register"
                            className="clear-btn"
                            style={{ textDecoration: "none", display: "inline-flex", alignItems: "center" }}
                        >
                            Register
                        </NavLink>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="app">
            <Navbar />

            <div className="hero">
                <span className="hero-badge">✦ Personal collection</span>
                <h1>💚 My Training Plan</h1>
                <p>Your hand-picked exercise collection — ready whenever you are</p>
                {plan.length > 0 && (
                    <div className="hero-stats">
                        <div><strong>{plan.length}</strong><span>Exercises saved</span></div>
                        <div><strong>{favorites.length}</strong><span>Favourites</span></div>
                        <div><strong>PDF</strong><span>Downloadable</span></div>
                    </div>
                )}
            </div>

            {error && (
                <div className="card" style={{ textAlign: "center", maxWidth: "620px" }}>
                    <p style={{ color: "#fecaca" }}>{error}</p>
                </div>
            )}

            {loading && plan.length === 0 ? (
                <div className="card" style={{ textAlign: "center", padding: "48px 32px", maxWidth: "480px" }}>
                    <div style={{ fontSize: "52px", marginBottom: "16px" }}>⏳</div>
                    <h3 style={{ color: "#bbf7d0", marginBottom: "12px", fontSize: "20px" }}>Loading your saved plan</h3>
                    <p style={{ color: "#94a3b8", lineHeight: "1.7" }}>
                        We’re fetching the exercises saved in your account.
                    </p>
                </div>
            ) : plan.length === 0 ? (
                <div className="card" style={{ textAlign: "center", padding: "48px 32px", maxWidth: "480px" }}>
                    <div style={{ fontSize: "52px", marginBottom: "16px" }}>🏋️</div>
                    <h3 style={{ color: "#bbf7d0", marginBottom: "12px", fontSize: "20px" }}>No exercises saved yet</h3>
                    <p style={{ color: "#94a3b8", lineHeight: "1.7", marginBottom: "24px" }}>
                        Ask the AI Coach a question, then save any exercise that interests you.
                        They'll all appear here.
                    </p>
                    <a
                        href="/"
                        style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "8px",
                            padding: "12px 24px",
                            borderRadius: "14px",
                            background: "linear-gradient(135deg, #16a34a, #22c55e)",
                            color: "#fff",
                            fontWeight: "700",
                            fontSize: "14px",
                            textDecoration: "none",
                            boxShadow: "0 6px 20px rgba(34,197,94,0.35)"
                        }}
                    >
                        💚 Go to AI Coach
                    </a>
                </div>
            ) : (
                <div className="exercise-wrapper my-plan-wrapper">
                    <div className="my-plan-actions">
                        <button
                            className="save-btn favorites-toggle-btn"
                            onClick={() => setShowFavoritesOnly((current) => !current)}
                        >
                            {showFavoritesOnly ? "Show All Exercises" : "Show Favorites"}
                        </button>

                        <button className="clear-btn" onClick={clearAll}>
                            🗑 Clear All
                        </button>
                    </div>

                    {visiblePlan.length === 0 ? (
                        <div className="card">
                            <p>No favorite exercises selected yet.</p>
                        </div>
                    ) : (
                        <div className="grid my-plan-grid">
                            {visiblePlan.map((ex, i) => {
                                const exerciseKey = getExerciseKey(ex);
                                const isFavorite = favorites.includes(exerciseKey);
                                const exerciseTitle = ex.raw || ex.name;

                                return (
                                    <div
                                        key={`${exerciseKey}-${i}`}
                                        className="exercise-card my-plan-card"
                                        onClick={() => openExerciseModal(ex)}
                                    >
                                        <button
                                            type="button"
                                            className={`favorite-heart ${isFavorite ? "is-favorite" : ""}`}
                                            onClick={(event) => {
                                                event.stopPropagation();
                                                toggleFavorite(ex);
                                            }}
                                            aria-label={isFavorite ? "Remove from favorites" : "Add to favorites"}
                                        >
                                            {isFavorite ? "♥" : "♡"}
                                        </button>

                                        <div className="image-row" style={{ justifyContent: "center", margin: 0 }}>
                                            {ex.images && ex.images.length > 0 ? (
                                                <img
                                                    src={ex.images[0]}
                                                    alt={exerciseTitle}
                                                    style={{
                                                        width: "100%",
                                                        height: "110px",
                                                        objectFit: "cover",
                                                        margin: 0
                                                    }}
                                                />
                                            ) : (
                                                <div style={{
                                                    width: "100%",
                                                    height: "110px",
                                                    background: "linear-gradient(135deg, rgba(34, 197, 94, 0.1), rgba(74, 222, 128, 0.05))",
                                                    display: "flex",
                                                    alignItems: "center",
                                                    justifyContent: "center",
                                                    fontSize: "32px"
                                                }}>
                                                    🏋️
                                                </div>
                                            )}
                                        </div>

                                        <div className="exercise-title">{exerciseTitle}</div>

                                        <button
                                            className="remove-btn"
                                            onClick={(event) => {
                                                event.stopPropagation();
                                                removeExercise(i);
                                            }}
                                        >
                                            ❌ Remove
                                        </button>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            )}

            {selectedExercise && (
                <div className="modal-overlay" onClick={closeExerciseModal}>
                    <div className="modal" onClick={(event) => event.stopPropagation()}>
                        <button className="close-btn" onClick={closeExerciseModal}>
                            ✖
                        </button>

                        <h2>{selectedExercise.label || selectedExercise.raw || selectedExercise.name}</h2>

                        <div className="modal-images">
                            {selectedExercise.images && selectedExercise.images.length > 0 ? (
                                selectedExercise.images.map((img, index) => (
                                    <img
                                        key={index}
                                        src={img}
                                        alt={selectedExercise.raw || selectedExercise.name}
                                        className="modal-img"
                                    />
                                ))
                            ) : (
                                <div className="image-placeholder">No images</div>
                            )}
                        </div>

                        <div className="video-section">
                            <button
                                className="small-video-btn"
                                onClick={() => setShowVideo((current) => !current)}
                            >
                                {showVideo ? "🙈 Hide video" : "🎥 Need help? Watch video"}
                            </button>

                            {showVideo && selectedExercise.video && !selectedExercise.video.includes("youtube.com/results?") && (
                                <iframe
                                    className="video-small"
                                    src={`${selectedExercise.video}?rel=0&modestbranding=1`}
                                    title={`${selectedExercise.label || selectedExercise.raw || selectedExercise.name} tutorial`}
                                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                    allowFullScreen
                                />
                            )}

                            {showVideo && selectedExercise.video && selectedExercise.video.includes("youtube.com/results?") && (
                                <a
                                    className="save-btn"
                                    href={selectedExercise.video}
                                    target="_blank"
                                    rel="noreferrer"
                                    style={{ marginTop: "12px", display: "inline-block", textDecoration: "none", width: "auto", padding: "10px 16px" }}
                                >
                                    Open matching YouTube results
                                </a>
                            )}
                        </div>

                        <p className="desc">{selectedExercise.raw || selectedExercise.name}</p>
                    </div>
                </div>
            )}
        </div>
    );
}