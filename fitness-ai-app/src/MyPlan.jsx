import { useEffect, useMemo, useState } from "react";
import Navbar from "./Navbar.jsx";
import { clearPlanMedia, deletePlanMedia, getManyPlanMedia, setPlanMedia } from "./lib/planMediaStore.js";

const API_BASE = "http://127.0.0.1:9000";

// Keeps media alive across in-app navigation without bloating localStorage.
const PLAN_MEDIA_CACHE = new Map();

function exerciseKey(ex) {
    return ex?.raw || ex?.name || "";
}

function stripPlanMedia(items) {
    return (items || []).map(({ images: _images, ...rest }) => ({ ...rest }));
}

export default function MyPlan() {
    const [plan, setPlan] = useState(() => {
        let stored = [];
        try { stored = JSON.parse(localStorage.getItem("myPlan") || "[]"); }
        catch { stored = []; }

        return stored.map((ex) => {
            const cached = PLAN_MEDIA_CACHE.get(exerciseKey(ex));
            return cached
                ? { ...ex, images: ex.images?.length ? ex.images : cached.images, video: ex.video || cached.video, label: ex.label || cached.label }
                : ex;
        });
    });
    const [favorites, setFavorites] = useState(() => {
        try { return JSON.parse(localStorage.getItem("favoriteExercises") || "[]"); }
        catch { return []; }
    });
    const [showFavoritesOnly, setShowFavoritesOnly] = useState(false);
    const [selectedExercise, setSelectedExercise] = useState(null);
    const [showVideo, setShowVideo] = useState(false);

    useEffect(() => {
        let cancelled = false;

        (async () => {
            const storedPlan = (() => {
                try { return JSON.parse(localStorage.getItem("myPlan") || "[]"); }
                catch { return []; }
            })();

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

            // Recover missing image/video for saved items (images were intentionally stripped for quota safety).
            const needsRecovery = withCache.some((ex) => {
                const hasImage = Array.isArray(ex.images) && ex.images.some(Boolean);
                return !hasImage || !ex.video;
            });

            if (!needsRecovery) return;

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
            // Persist lightweight rows only; media is cached in-memory + IndexedDB.
            localStorage.setItem("myPlan", JSON.stringify(stripPlanMedia(recovered)));
        })();

        return () => { cancelled = true; };
    }, []);

    const getExerciseKey = (exercise) => exercise.raw || exercise.name;

    const removeExercise = (index) => {
        const updated = [...plan];
        const removed = updated[index];
        updated.splice(index, 1);

        setPlan(updated);
        localStorage.setItem("myPlan", JSON.stringify(stripPlanMedia(updated)));

        if (removed) {
            const removedKey = getExerciseKey(removed);
            PLAN_MEDIA_CACHE.delete(removedKey);
            deletePlanMedia(removedKey);
            const updatedFavorites = favorites.filter((key) => key !== removedKey);
            setFavorites(updatedFavorites);
            localStorage.setItem("favoriteExercises", JSON.stringify(updatedFavorites));
        }
    };

    const clearAll = () => {
        localStorage.removeItem("myPlan");
        localStorage.removeItem("favoriteExercises");
        PLAN_MEDIA_CACHE.clear();
        clearPlanMedia();
        setPlan([]);
        setFavorites([]);
        setShowFavoritesOnly(false);
    };

    const toggleFavorite = (exercise) => {
        const key = getExerciseKey(exercise);
        const updatedFavorites = favorites.includes(key)
            ? favorites.filter((item) => item !== key)
            : [...favorites, key];

        setFavorites(updatedFavorites);
        localStorage.setItem("favoriteExercises", JSON.stringify(updatedFavorites));
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

    return (
        <div className="app">
            <Navbar />

            <div className="hero">
                <h1>💚 My Training Plan</h1>
                <p>Your saved exercises</p>
            </div>

            {plan.length === 0 ? (
                <div className="card">
                    <p>No exercises saved yet 😢</p>
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