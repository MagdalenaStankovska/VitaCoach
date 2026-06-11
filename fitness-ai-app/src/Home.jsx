import { useState, useEffect, useRef } from "react";
import { NavLink } from "react-router-dom";
import { jsPDF } from "jspdf";
import Navbar from "./Navbar.jsx";
import { setPlanMedia } from "./lib/planMediaStore.js";
import { fetchUserPlan, saveUserPlan } from "./lib/api.js";
import { useAuth } from "./auth/AuthContext.jsx";

const promptIdeas = [
    "Build stronger legs with dumbbells",
    "Best exercises for core strength",
    "Workout for fat loss at home",
    "How do I improve posture and core stability?",
    "I only have 20 minutes per day - what should I do?",
    "Create a beginner weekly workout split for me",
    "How can I gain muscle without gaining too much fat?",
    "Give me a low-impact plan for knee pain",
    "How many rest days should I take each week?",
    "What should I eat before and after training?",
    "Can you make a home workout with no equipment?",
    "How do I break a workout plateau safely?",
    "Design a 4-week plan to improve endurance",
    "What warm-up should I do before leg day?",
];

const VISIBLE_PROMPTS = 4;

// ─── strip large base64 images before persisting to localStorage ─────────────
function stripImages(exercises) {
    return (exercises || []).map((ex) => ({ ...ex, images: [] }));
}

// Module-level cache — keeps the last full API response including images
// so if user navigates away and comes back, images are still available
let _lastFullResponse = null;

function shuffleArray(items) {
    const copy = [...items];
    for (let i = copy.length - 1; i > 0; i -= 1) {
        const j = Math.floor(Math.random() * (i + 1));
        [copy[i], copy[j]] = [copy[j], copy[i]];
    }
    return copy;
}

function getRandomPrompts(count = VISIBLE_PROMPTS) {
    return shuffleArray(promptIdeas).slice(0, count);
}

// Keywords that mark each section – order matters for the regex alternation
const QUICK_KEYWORDS  = "short answer|quick advice|summary|in short";
const DETAIL_KEYWORDS = "full plan|detailed answer|detailed plan|plan details|full answer|workout plan|training plan";

// Matches a section header line/inline regardless of surrounding **, ##, 1), etc.
// e.g.  "SHORT ANSWER:", "**Short Answer:**", "## Full Plan", "1) Detailed Answer:"
const QUICK_RE  = new RegExp(
    "(?:^|\\n)[\\t ]*(?:\\*{1,2}|#{1,6}[\\t ]*)?[\\t ]*(?:\\d+[.)][\\t ]*)?(?:" + QUICK_KEYWORDS  + ")[\\t ]*(?:\\*{1,2})?[\\t ]*:?[\\t ]*",
    "i"
);
const DETAIL_RE = new RegExp(
    "(?:^|\\n)[\\t ]*(?:\\*{1,2}|#{1,6}[\\t ]*)?[\\t ]*(?:\\d+[.)][\\t ]*)?(?:" + DETAIL_KEYWORDS + ")[\\t ]*(?:\\*{1,2})?[\\t ]*:?[\\t ]*",
    "i"
);

function splitAnswerSections(rawAnswer) {
    const text = (rawAnswer || "").replace(/\r\n/g, "\n").trim();
    if (!text) return { quickAdvice: "", fullPlan: "" };

    const qm = QUICK_RE.exec(text);
    const dm = DETAIL_RE.exec(text);

    if (qm && dm) {
        const qStart = qm.index + qm[0].length;
        const dStart = dm.index + dm[0].length;
        if (qStart <= dStart) {
            // Normal order: SHORT ANSWER … FULL PLAN …
            return {
                quickAdvice: text.slice(qStart, dm.index).trim(),
                fullPlan:    text.slice(dStart).trim(),
            };
        }
        // Reversed (unusual): FULL PLAN … SHORT ANSWER …
        return {
            quickAdvice: text.slice(qStart).trim(),
            fullPlan:    text.slice(dStart, qm.index).trim(),
        };
    }

    if (qm) {
        // Only a quick section found – use its content as quick advice, full text as plan
        return {
            quickAdvice: text.slice(qm.index + qm[0].length).trim(),
            fullPlan:    text.trim(),
        };
    }

    if (dm) {
        // Only a detail section found – everything before it becomes the quick advice
        const before   = text.slice(0, dm.index).trim();
        const fullPlan = text.slice(dm.index + dm[0].length).trim();
        return {
            quickAdvice: before || fullPlan.split(/\n\s*\n/)[0].trim(),
            fullPlan,
        };
    }

    // Last resort: first paragraph = quick advice, remainder = full plan
    const blocks = text.split(/\n\s*\n+/).map((b) => b.trim()).filter(Boolean);
    if (blocks.length === 1) return { quickAdvice: blocks[0], fullPlan: blocks[0] };
    return {
        quickAdvice: blocks[0],
        fullPlan:    blocks.slice(1).join("\n\n"),
    };
}

// Section labels to strip from displayed content (case-insensitive, whole line)
const SECTION_LABEL_RE = new RegExp(
    "^[\\t ]*(?:\\*{1,2}|#{1,6}[\\t ]*)?[\\t ]*(?:\\d+[.)][\\t ]*)?(?:" +
    QUICK_KEYWORDS + "|" + DETAIL_KEYWORDS +
    ")[\\t ]*(?:\\*{1,2})?[\\t ]*:?[\\t ]*$",
    "gim"
);

function cleanDisplayText(text) {
    return (text || "")
        .replace(/\r\n/g, "\n")
        .replace(/\*\*/g, "")
        .replace(/__/g, "")
        .replace(/^\s{0,3}#{1,6}\s*/gm, "")
        .replace(/^>\s?/gm, "")
        .replace(SECTION_LABEL_RE, "")
        .replace(/\n{3,}/g, "\n\n")
        .trim();
}

function buildAnswerBlocks(text) {
    const cleaned = cleanDisplayText(text);
    if (!cleaned) return [];

    const listPattern = /^([-*•]\s+|\d+[.)]\s+)/;
    const titlePattern = /^[A-Za-z][A-Za-z\s/&-]{1,40}:$/;

    return cleaned
        .split(/\n\s*\n+/)
        .map((block) => block.trim())
        .filter(Boolean)
        .map((block) => {
            const lines = block.split("\n").map((line) => line.trim()).filter(Boolean);
            if (lines.length === 0) return null;

            if (titlePattern.test(lines[0]) && lines.length > 1) {
                const title = lines[0].replace(/:$/, "");
                const contentLines = lines.slice(1);
                if (contentLines.every((line) => listPattern.test(line))) {
                    return {
                        type: "section-list",
                        title,
                        items: contentLines.map((line) => line.replace(listPattern, "").trim()),
                    };
                }

                return {
                    type: "section-text",
                    title,
                    text: contentLines.join(" "),
                };
            }

            if (lines.every((line) => listPattern.test(line))) {
                return {
                    type: "list",
                    items: lines.map((line) => line.replace(listPattern, "").trim()),
                };
            }

            return {
                type: "text",
                text: lines.join(" "),
            };
        })
        .filter(Boolean);
}

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
    const { isAuthenticated, token } = useAuth();
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
    const [toast, setToast] = useState(null);
    const [showVideo, setShowVideo] = useState(false);
    const [selectedExercise, setSelectedExercise] = useState(null);
    const [suggestedPrompts, setSuggestedPrompts] = useState(() => getRandomPrompts());

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
            showToast("Your answer is ready!", "success", "AI update");
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
                        showToast("Exercises refreshed with images.", "success", "Exercise sync");
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

    function showToast(message, type = "success", title = "VitaCoach") {
        setToast({ message, type, title });
        clearTimeout(toastTimer.current);
        toastTimer.current = setTimeout(() => setToast(null), 4000);
    }

    // Persist question
    useEffect(() => { localStorage.setItem("aiQuestion", question); }, [question]);

    const { quickAdvice: shortAnswer, fullPlan: fullPlanAnswer } = splitAnswerSections(answer);
    const cleanShortAnswer = cleanDisplayText(shortAnswer);
    const cleanFullPlanAnswer = cleanDisplayText(fullPlanAnswer);
    const quickAdviceBlocks = buildAnswerBlocks(shortAnswer);
    const fullPlanBlocks = buildAnswerBlocks(fullPlanAnswer);

    const refreshSuggestedPrompts = () => setSuggestedPrompts(getRandomPrompts());

    const askAI = () => {
        if (!question.trim()) return;

        setLoading(true);
        setToast(null);
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
                showToast("Answer updated!", "success", "AI update");
                refreshSuggestedPrompts();
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
        writeWrapped(cleanFullPlanAnswer || cleanDisplayText(answer));
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
        if (!isAuthenticated || !token) {
            showToast("Please log in to save exercises to your plan.", "warning", "Login required");
            return;
        }

        const displayName = exercise.raw || exercise.name;
        let current = [];

        try {
            const response = await fetchUserPlan(token);
            current = Array.isArray(response.items) ? response.items : [];
        } catch (e) {
            showToast(e.message || "Could not load your saved plan.", "error", "Save failed");
            return;
        }

        if (current.find((e) => (e.raw || e.name) === displayName)) {
            showToast("This exercise is already saved in My Plan.", "warning", "Already saved");
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
            await saveUserPlan(token, [...current, item]);

            // Best-effort media persistence so cards survive full browser refresh.
            await setPlanMedia(displayName, {
                label: exercise.label,
                images: Array.isArray(exercise.images) ? exercise.images.filter(Boolean) : [],
                video: exercise.video || "",
            });

            showToast(`${exercise.label || exercise.name} was added to My Plan.`, "success", "Saved successfully");
        } catch (e) {
            if (e.name === "QuotaExceededError") {
                showToast("Your plan storage is full. Remove a few saved exercises, then try again.", "error", "Storage full");
            } else {
                showToast(`Could not save this exercise: ${e.message}`, "error", "Save failed");
            }
        }
    };

    return (
        <div className="app">
            <Navbar />

            {/* TOAST */}
            {toast && (
                <div className={`answer-toast answer-toast-${toast.type}`} role="status" aria-live="polite">
                    <div className="answer-toast-icon" aria-hidden="true">
                        {toast.type === "error" ? "⚠️" : toast.type === "warning" ? "📌" : "💚"}
                    </div>
                    <div className="answer-toast-copy">
                        <strong>{toast.title}</strong>
                        <span>{toast.message}</span>
                    </div>
                    <button type="button" className="answer-toast-close" onClick={() => setToast(null)}>
                        ✕
                    </button>
                </div>
            )}

            {/* HERO */}
            <div className="hero hero-premium">
                <span className="hero-badge">✦ AI fitness studio</span>
                <h1>Train smarter with AI</h1>
                <p>Your personalized fitness coach — ask anything, get a plan, train better.</p>
                <div className="hero-stats">
                    <div><strong>8</strong><span>Exercises per answer</span></div>
                    <div><strong>Live</strong><span>Background generation</span></div>
                    <div><strong>Visual</strong><span>Image + video guides</span></div>
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
                {suggestedPrompts.map((idea) => (
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
                        <div className="answer-body answer-body-quick">
                            {quickAdviceBlocks.length > 0 ? quickAdviceBlocks.map((block, index) => (
                                <div key={`quick-${index}`} className="answer-block answer-block-quick">
                                    {block.title && <h4 className="answer-block-title">{block.title}</h4>}
                                    {block.items ? (
                                        <ul className="answer-list">
                                            {block.items.map((item, itemIndex) => (
                                                <li key={`quick-item-${itemIndex}`}>{item}</li>
                                            ))}
                                        </ul>
                                    ) : (
                                        <p className="answer-paragraph">{block.text}</p>
                                    )}
                                </div>
                            )) : <p className="answer-paragraph">{cleanShortAnswer}</p>}
                        </div>
                    </div>

                    <div className={`card long-card${loading ? " card-stale" : ""}`}>
                        <h3>📋 Full Plan</h3>
                        <div className="answer-body answer-body-plan">
                            {fullPlanBlocks.length > 0 ? fullPlanBlocks.map((block, index) => (
                                <div key={`plan-${index}`} className="answer-block">
                                    {block.title && <h4 className="answer-block-title">{block.title}</h4>}
                                    {block.items ? (
                                        <ul className="answer-list">
                                            {block.items.map((item, itemIndex) => (
                                                <li key={`plan-item-${itemIndex}`}>{item}</li>
                                            ))}
                                        </ul>
                                    ) : (
                                        <p className="answer-paragraph">{block.text}</p>
                                    )}
                                </div>
                            )) : <p className="answer-paragraph">{cleanFullPlanAnswer}</p>}
                        </div>
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

                        <div className="modal-header">
                            <span className="modal-kicker">Exercise spotlight</span>
                            <h2>{selectedExercise.label || selectedExercise.name}</h2>
                        </div>

                        {/* Images */}
                        <div className="modal-images">
                            {selectedExercise.images && selectedExercise.images.filter(Boolean).length > 0 ? (
                                selectedExercise.images.filter(Boolean).map((img, i) => (
                                    <img key={i} src={img} alt={selectedExercise.label || selectedExercise.name} className="modal-img" />
                                ))
                            ) : (
                                <div className="modal-image-placeholder">No preview image available</div>
                            )}
                        </div>

                        {/* Full RAG sentence as description */}
                        <div className="modal-copy">
                            <p className="desc">{selectedExercise.raw}</p>
                        </div>

                        {/* VIDEO — toggle button, then iframe */}
                        <div className="video-section">
                            <div className="video-section-header">
                                <span className="video-section-kicker">Form support</span>
                                <button
                                    className="small-video-btn"
                                    onClick={() => setShowVideo((v) => !v)}
                                >
                                    {showVideo ? "🙈 Hide video" : "🎥 Watch tutorial"}
                                </button>
                            </div>

                            {showVideo && selectedExercise.video && !selectedExercise.video.includes("youtube.com/results?") && (
                                <div className="video-frame">
                                    <iframe
                                        className="video-small"
                                        src={`${selectedExercise.video}?rel=0&modestbranding=1`}
                                        title={`${selectedExercise.label || selectedExercise.name} tutorial`}
                                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                        allowFullScreen
                                    />
                                </div>
                            )}

                            {showVideo && selectedExercise.video && selectedExercise.video.includes("youtube.com/results?") && (
                                <a
                                    className="save-btn modal-link-btn"
                                    href={selectedExercise.video}
                                    target="_blank"
                                    rel="noreferrer"
                                >
                                    Open matching YouTube results
                                </a>
                            )}
                        </div>

                        <div className="modal-actions">
                            <button className="save-btn" onClick={() => saveToPlan(selectedExercise)}>
                                💚 Save to My Plan
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
