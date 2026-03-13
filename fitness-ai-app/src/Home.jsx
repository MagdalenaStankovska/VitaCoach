import { useState, useEffect, useRef } from "react";
import { NavLink } from "react-router-dom";
import { jsPDF } from "jspdf";
import Navbar from "./Navbar.jsx";
import { setPlanMedia } from "./lib/planMediaStore.js";

const promptIdeas = [
    "Build stronger legs with dumbbells",
    "Best exercises for core strength",
    "Workout for fat loss at home",
    "How do I improve posture and core stability?",
];

// ─── strip large base64 images before persisting to localStorage ─────────────
function stripImages(exercises) {
    return (exercises || []).map((ex) => ({ ...ex, images: [] }));
}

// Module-level cache — keeps the last full API response including images
// so if user navigates away and comes back, images are still available
let _lastFullResponse = null;

// ─── background fetch helper ─────────────────────────────────────────────────
function runBackgroundAsk(question, onDone) {
    const requestId = Date.now();
    sessionStorage.setItem("pendingRequestId", String(requestId));
    sessionStorage.setItem("pendingQuestion", question);

    fetch("http://127.0.0.1:9000/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
    })
        .then((r) => r.json())
        .then((data) => {
            // Keep full data (with images) in memory
            _lastFullResponse = data;
            // Persist text-only to localStorage (no base64 images — quota safe)
            localStorage.setItem("aiAnswer", data.answer || "");
            localStorage.setItem("aiExercises", JSON.stringify(stripImages(data.exercises || [])));
            sessionStorage.setItem("answerReady", String(requestId));
            sessionStorage.removeItem("pendingRequestId");
            onDone(data, requestId, null);
        })
        .catch(() => {
            const msg = "Error connecting to AI server.";
            _lastFullResponse = null;
            localStorage.setItem("aiAnswer", msg);
            localStorage.setItem("aiExercises", "[]");
            sessionStorage.setItem("answerReady", String(requestId));
            sessionStorage.removeItem("pendingRequestId");
            onDone(null, requestId, msg);
        });

    return requestId;
}

// ─────────────────────────────────────────────────────────────────────────────

export default function Home() {
    const [question, setQuestion] = useState(() => localStorage.getItem("aiQuestion") || "");
    const [answer, setAnswer] = useState(() => _lastFullResponse?.answer || localStorage.getItem("aiAnswer") || "");
    const [exercises, setExercises] = useState(() => {
        if (_lastFullResponse?.exercises?.length) return _lastFullResponse.exercises;
        try { return JSON.parse(localStorage.getItem("aiExercises") || "[]"); }
        catch { return []; }
    });
    const [loading, setLoading] = useState(
        () => !!sessionStorage.getItem("pendingRequestId")
    );
    const [toast, setToast] = useState(""); // "Answer is ready!" notification
    const [showVideo, setShowVideo] = useState(false);
    const [selectedExercise, setSelectedExercise] = useState(null);

    const mountedRef = useRef(true);
    const toastTimer = useRef(null);

    // Detect if a request finished while we were on another page
    useEffect(() => {
        // Clean up any old base64 blobs from localStorage
        try {
            const stored = JSON.parse(localStorage.getItem("aiExercises") || "[]");
            if (stored.some((ex) => (ex.images || []).some((img) => img && img.startsWith("data:")))) {
                localStorage.setItem("aiExercises", JSON.stringify(stripImages(stored)));
            }
        } catch { /* ignore */ }

        // Keep in-memory full response in sync so remount preserves images.
        if (!_lastFullResponse && answer) {
            _lastFullResponse = { answer, exercises };
        }

        const readyId = sessionStorage.getItem("answerReady");
        if (readyId) {
            sessionStorage.removeItem("answerReady");
            // Prefer module-level cache (has images), fall back to localStorage (no images)
            if (_lastFullResponse) {
                setAnswer(_lastFullResponse.answer || "");
                setExercises(_lastFullResponse.exercises || []);
            } else {
                setAnswer(localStorage.getItem("aiAnswer") || "");
                try { setExercises(JSON.parse(localStorage.getItem("aiExercises") || "[]")); } catch { setExercises([]); }
            }
            setLoading(false);
            showToast("✅ Your answer is ready!");
        }

        // If we only have stripped localStorage exercises (no images), refresh once from backend.
        const storedQuestion = localStorage.getItem("aiQuestion") || "";
        const storedAnswer = localStorage.getItem("aiAnswer") || "";
        const hasExercises = Array.isArray(exercises) && exercises.length > 0;
        const hasAnyImage = hasExercises && exercises.some((ex) => Array.isArray(ex.images) && ex.images.some(Boolean));

        if (!readyId && storedQuestion && storedAnswer && hasExercises && !hasAnyImage) {
            fetch("http://127.0.0.1:9000/ask", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ question: storedQuestion }),
            })
                .then((r) => r.json())
                .then((data) => {
                    _lastFullResponse = data;
                    if (mountedRef.current) {
                        setAnswer(data.answer || storedAnswer);
                        setExercises(data.exercises || []);
                        showToast("✅ Exercises refreshed with images");
                    }
                    // Keep localStorage lightweight
                    localStorage.setItem("aiAnswer", data.answer || storedAnswer);
                    localStorage.setItem("aiExercises", JSON.stringify(stripImages(data.exercises || [])));
                })
                .catch(() => {
                    // Keep current text answer even if refresh fails
                    if (mountedRef.current) {
                        setAnswer(storedAnswer);
                    }
                });
        }

        return () => { mountedRef.current = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Keep module-level cache fresh while user is on Home.
    useEffect(() => {
        if (answer || (Array.isArray(exercises) && exercises.length > 0)) {
            _lastFullResponse = { answer, exercises };
        }
    }, [answer, exercises]);

    function showToast(msg) {
        setToast(msg);
        clearTimeout(toastTimer.current);
        toastTimer.current = setTimeout(() => setToast(""), 4000);
    }

    // Persist question
    useEffect(() => { localStorage.setItem("aiQuestion", question); }, [question]);

    const shortAnswer = answer
        ? (answer.split("\n\n")[0] || answer).replace(/\s+/g, " ").trim()
        : "";

    const askAI = () => {
        if (!question.trim()) return;

        setLoading(true);
        setToast("");
        setSelectedExercise(null);
        setShowVideo(false);
        // Keep old answer visible while loading – don't clear it

        runBackgroundAsk(question, (data, _reqId, error) => {
            if (error) {
                if (mountedRef.current) { setAnswer(error); setExercises([]); }
            } else {
                // Always use the fresh data with full images, whether mounted or not
                if (mountedRef.current) {
                    setAnswer(data.answer || "");
                    setExercises(data.exercises || []);
                }
            }
            if (mountedRef.current) {
                setLoading(false);
                showToast("✅ Answer updated!");
            }
        });
    };

    const downloadPlan = () => {
        if (!answer) return;

        const doc = new jsPDF({ unit: "pt", format: "a4" });
        const pageWidth = doc.internal.pageSize.getWidth();
        const pageHeight = doc.internal.pageSize.getHeight();
        const margin = 40;
        const maxWidth = pageWidth - margin * 2;
        const lineHeight = 16;
        let y = margin;

        const ensureSpace = (needed = lineHeight) => {
            if (y + needed > pageHeight - margin) {
                doc.addPage();
                y = margin;
            }
        };

        const writeWrapped = (text, size = 12) => {
            doc.setFontSize(size);
            const lines = doc.splitTextToSize(text || "", maxWidth);
            lines.forEach((line) => {
                ensureSpace();
                doc.text(line, margin, y);
                y += lineHeight;
            });
        };

        doc.setFont("helvetica", "bold");
        doc.setFontSize(18);
        doc.text("VITACOACH PLAN", margin, y);
        y += 28;

        doc.setFont("helvetica", "bold");
        doc.setFontSize(13);
        ensureSpace();
        doc.text("ADVICE", margin, y);
        y += 18;

        doc.setFont("helvetica", "normal");
        writeWrapped(answer);
        y += 8;

        if (exercises.length > 0) {
            doc.setFont("helvetica", "bold");
            doc.setFontSize(13);
            ensureSpace(24);
            doc.text("EXERCISES", margin, y);
            y += 18;

            exercises.forEach((ex, i) => {
                doc.setFont("helvetica", "bold");
                writeWrapped(`${i + 1}. ${ex.name}`, 12);

                doc.setFont("helvetica", "normal");
                writeWrapped(ex.raw || "", 11);
                y += 8;
            });
        }

        doc.save("VitaCoach-Plan.pdf");
    };

    const saveToPlan = async (exercise) => {
        const displayName = exercise.raw || exercise.name;
        let current = [];
        try { current = JSON.parse(localStorage.getItem("myPlan") || "[]"); } catch { current = []; }

        if (current.find((e) => (e.raw || e.name) === displayName)) {
            alert("Already in your plan 👍");
            return;
        }

        // Save only lightweight fields — media is persisted in IndexedDB.
        const item = {
            name: exercise.name,
            raw: exercise.raw || exercise.name,
            label: exercise.label,
            video: exercise.video,
        };

        try {
            localStorage.setItem("myPlan", JSON.stringify([...current, item]));

            // Best-effort media persistence so cards survive full browser refresh.
            await setPlanMedia(displayName, {
                label: exercise.label,
                images: Array.isArray(exercise.images) ? exercise.images.filter(Boolean) : [],
                video: exercise.video || "",
            });

            alert("Saved to My Plan 💚");
        } catch (e) {
            if (e.name === "QuotaExceededError") {
                alert("Your plan storage is full. Go to My Plan and remove some exercises first.");
            } else {
                alert("Could not save: " + e.message);
            }
        }
    };

    return (
        <div className="app">
            <Navbar />

            {/* TOAST */}
            {toast && <div className="answer-toast">{toast}</div>}

            {/* HERO */}
            <div className="hero hero-premium">
                <span className="hero-badge">AI fitness studio</span>
                <h1>Train smarter with AI</h1>
                <p>Your personalized fitness coach — ask a question, browse freely, come back to your plan.</p>
                <div className="hero-stats">
                    <div><strong>8</strong><span>RAG exercise picks</span></div>
                    <div><strong>Live</strong><span>Generates in background</span></div>
                    <div><strong>Visual</strong><span>Image + matched video</span></div>
                </div>
            </div>

            {/* LOADING BANNER – visible on every page via fixed positioning */}
            {loading && (
                <div className="loading-banner">
                    <div className="loading-banner-left">
                        <span className="loading-spinner" />
                        <div>
                            <strong>Generating your answer…</strong>
                            <p>Feel free to browse — we&apos;ll notify you when it&apos;s ready.</p>
                        </div>
                    </div>
                    <div className="loading-banner-actions">
                        <NavLink to="/trainings" className="loading-nav-link">📋 Trainings</NavLink>
                        <NavLink to="/my-plan" className="loading-nav-link">💪 My Plan</NavLink>
                    </div>
                </div>
            )}

            {/* ASK */}
            <div className="ask-section ask-fancy">
                <textarea
                    rows="3"
                    placeholder="Ask anything — 'Best leg exercises', 'Build abs in 4 weeks'…"
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); askAI(); } }}
                />
                <button onClick={askAI} disabled={loading}>
                    {loading ? "Generating…" : "💚 Ask VitaCoach"}
                </button>
                {loading && <div className="green-loader" />}
            </div>

            {/* PROMPT CHIPS */}
            <div className="prompt-chip-row">
                {promptIdeas.map((idea) => (
                    <button
                        key={idea}
                        type="button"
                        className="prompt-chip"
                        onClick={() => setQuestion(idea)}
                    >
                        {idea}
                    </button>
                ))}
            </div>

            {/* ANSWER */}
            {answer && (
                <div className="answer-stack">
                    <div className="answer-meta-row">
                        <span className="answer-kicker">
                            {loading ? "⏳ Updating…" : "✅ AI response ready"}
                        </span>
                        <span className="answer-pill">
                            {exercises.length} exercise{exercises.length === 1 ? "" : "s"} recommended
                        </span>
                    </div>

                    <div className={`card short-card${loading ? " card-stale" : ""}`}>
                        <h3>💡 Quick Advice</h3>
                        <p>{shortAnswer}</p>
                    </div>

                    <div className={`card long-card${loading ? " card-stale" : ""}`}>
                        <h3>📋 Full Plan</h3>
                        <p style={{ whiteSpace: "pre-wrap" }}>{answer}</p>
                    </div>

                    <div style={{ textAlign: "center", marginTop: "20px" }}>
                        <button className="save-btn" onClick={downloadPlan}>⬇️ Download My Plan</button>
                    </div>
                </div>
            )}

            {/* EXERCISES */}
            {exercises.length > 0 && (
                <div className="exercise-wrapper">
                    <h3>🏋️ Recommended Exercises</h3>
                    <div className="grid">
                        {exercises.map((ex, i) => (
                            <div
                                key={`${ex.label || ex.name}-${i}`}
                                className="exercise-card"
                                onClick={() => { setSelectedExercise(ex); setShowVideo(false); }}
                            >
                                <div className="exercise-rank">#{i + 1}</div>
                                <div className="image-row">
                                    {ex.images && ex.images.filter(Boolean).length > 0 ? (
                                        ex.images.filter(Boolean).map((img, idx) => (
                                            <img key={idx} src={img} alt={ex.label || ex.name} className="exercise-img" />
                                        ))
                                    ) : (
                                        <div className="image-placeholder">🏋️</div>
                                    )}
                                </div>
                                {/* Show the FULL RAG sentence as the card title */}
                                <div className="exercise-title">{ex.name}</div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* MODAL */}
            {selectedExercise && (
                <div className="modal-overlay" onClick={() => { setSelectedExercise(null); setShowVideo(false); }}>
                    <div className="modal" onClick={(e) => e.stopPropagation()}>
                        <button className="close-btn" onClick={() => { setSelectedExercise(null); setShowVideo(false); }}>✖</button>

                        {/* Clean label as heading */}
                        <h2>{selectedExercise.label || selectedExercise.name}</h2>

                        {/* Images */}
                        <div className="modal-images">
                            {selectedExercise.images && selectedExercise.images.filter(Boolean).map((img, i) => (
                                <img key={i} src={img} alt={selectedExercise.label || selectedExercise.name} className="modal-img" />
                            ))}
                        </div>

                        {/* Full RAG sentence as description */}
                        <p className="desc">{selectedExercise.raw}</p>

                        {/* VIDEO — toggle button, then iframe */}
                        <div className="video-section">
                            <button
                                className="small-video-btn"
                                onClick={() => setShowVideo((v) => !v)}
                            >
                                {showVideo ? "🙈 Hide video" : "🎥 Need help? Watch video"}
                            </button>

                            {showVideo && selectedExercise.video && !selectedExercise.video.includes("youtube.com/results?") && (
                                <iframe
                                    className="video-small"
                                    src={`${selectedExercise.video}?rel=0&modestbranding=1`}
                                    title={`${selectedExercise.label || selectedExercise.name} tutorial`}
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

                        <button className="save-btn" onClick={() => saveToPlan(selectedExercise)}>
                            💚 Save to My Plan
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
