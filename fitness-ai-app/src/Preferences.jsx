import { useEffect, useState } from "react";
import Navbar from "./Navbar.jsx";
import "./Preferences.css";
import { useAuth } from "./auth/AuthContext.jsx";
import { fetchUserPreferences, saveUserPreferences, analyzeUserPreferences } from "./lib/api.js";

export default function Preferences() {
    const { isAuthenticated, token, initializing } = useAuth();
    const [prefs, setPrefs] = useState({ goal: "", height_cm: "", weight_kg: "", gender: "", age: "", bmr: null, tdee: null });
    const [imagePreview, setImagePreview] = useState(null);
    const [loading, setLoading] = useState(false);
    const [message, setMessage] = useState("");
    const [analysis, setAnalysis] = useState(null);

    useEffect(() => {
        if (!isAuthenticated || !token) return;
        let cancelled = false;
        setLoading(true);
        fetchUserPreferences(token)
            .then((data) => {
                if (cancelled) return;
                const p = data.preferences || {};
                setPrefs({
                    goal: p.goal || "",
                    height_cm: p.height_cm || "",
                    weight_kg: p.weight_kg || "",
                    gender: p.gender || "",
                    age: p.age || "",
                    bmr: p.bmr ?? null,
                    tdee: p.tdee ?? null,
                    bloodTestImage: p.bloodTestImage || null,
                });
                // bloodTestImage is encrypted at rest — the server only ever
                // returns a renderable data URL right after a fresh upload in
                // this same session. Once persisted/reloaded it comes back as
                // an opaque encrypted token, which we don't try to preview.
                if (p.bloodTestImage && p.bloodTestImage.startsWith("data:")) {
                    setImagePreview(p.bloodTestImage);
                } else {
                    setImagePreview(null);
                }
            })
            .catch((err) => {
                console.error("Failed to load preferences", err);
                setMessage("Failed to load preferences: " + err.message);
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });

        return () => {
            cancelled = true;
        };
    }, [isAuthenticated, token]);

    if (!initializing && !isAuthenticated) {
        return (
            <div className="app">
                <Navbar />
                <div className="preferences-container" style={{ textAlign: "center", paddingTop: 40 }}>
                    <div className="prefs-form-card">
                        <h2 style={{ fontSize: 24, marginBottom: 12 }}>🔒 Access Denied</h2>
                        <p style={{ color: "#cbd5e1" }}>Please log in to manage your preferences.</p>
                    </div>
                </div>
            </div>
        );
    }

    function onFileChange(e) {
        const file = e.target.files && e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = () => {
            const dataUrl = reader.result;
            setImagePreview(dataUrl);
            setPrefs((p) => ({ ...p, bloodTestImage: dataUrl }));
        };
        reader.readAsDataURL(file);
    }

    function onChange(e) {
        const { name, value } = e.target;
        setPrefs((p) => ({ ...p, [name]: value }));
    }

    async function onSave(e) {
        e.preventDefault();
        setLoading(true);
        setMessage("");
        try {
            const toSave = {
                goal: prefs.goal || null,
                height_cm: prefs.height_cm ? Number(prefs.height_cm) : null,
                weight_kg: prefs.weight_kg ? Number(prefs.weight_kg) : null,
                gender: prefs.gender || null,
                age: prefs.age ? Number(prefs.age) : null,
                bloodTestImage: prefs.bloodTestImage || null,
            };
            const res = await saveUserPreferences(token, toSave);
            const saved = res.preferences || {};
            setPrefs((p) => ({ ...p, bmr: saved.bmr ?? null, tdee: saved.tdee ?? null }));
            setMessage("✅ Your preferences have been saved successfully!");
            setAnalysis(null);
        } catch (err) {
            console.error(err);
            setMessage("❌ Save failed: " + err.message);
        } finally {
            setLoading(false);
        }
    }

    async function onAnalyze(e) {
        e.preventDefault();
        setLoading(true);
        setMessage("");
        setAnalysis(null);
        try {
            const res = await analyzeUserPreferences(token);
            setAnalysis(res.analysis || JSON.stringify(res));
        } catch (err) {
            console.error(err);
            setMessage("⚠️ Analysis failed: " + err.message);
        } finally {
            setLoading(false);
        }
    }

    return (
        <div className="app">
            <Navbar />

            <div className="preferences-hero">
                <h1>💎 Your Fitness Profile</h1>
                <p>Personalize your health goals and let our AI coach adapt to your needs</p>
            </div>

            <div className="preferences-container">
                {message && (
                    <div className={`prefs-message ${message.startsWith("✅") ? "prefs-message-success" : "prefs-message-error"}`}>
                        <span className="prefs-message-icon">{message.startsWith("✅") ? "✨" : "⚠️"}</span>
                        <span>{message}</span>
                    </div>
                )}

                <div className="prefs-form-card">
                    <form onSubmit={onSave}>
                        {/* ─── GOALS SECTION ─────────────────────────── */}
                        <div className="prefs-section">
                            <h3>
                                <span className="prefs-section-emoji">🎯</span>
                                Your Fitness Goal
                            </h3>
                            <div className="prefs-form-row">
                                <div className="prefs-form-group">
                                    <label>
                                        <span className="prefs-label-emoji">🏆</span>
                                        Primary Goal
                                    </label>
                                    <select
                                        name="goal"
                                        value={prefs.goal}
                                        onChange={onChange}
                                        className="prefs-select"
                                    >
                                        <option value="">-- select your goal --</option>
                                        <option value="weight_loss">💪 Weight Loss</option>
                                        <option value="muscle_gain">🔥 Muscle Gain</option>
                                        <option value="maintain">⚖️ Maintain Weight</option>
                                        <option value="general_fitness">✨ General Fitness</option>
                                    </select>
                                </div>
                            </div>
                        </div>

                        {/* ─── PERSONAL METRICS SECTION ─────────────── */}
                        <div className="prefs-section">
                            <h3>
                                <span className="prefs-section-emoji">📊</span>
                                Personal Metrics
                            </h3>
                            <div className="prefs-form-row">
                                <div className="prefs-form-group">
                                    <label>
                                        <span className="prefs-label-emoji">📏</span>
                                        Height (cm)
                                    </label>
                                    <input
                                        name="height_cm"
                                        type="number"
                                        placeholder="e.g., 180"
                                        value={prefs.height_cm}
                                        onChange={onChange}
                                        className="prefs-input"
                                        min="100"
                                        max="250"
                                    />
                                </div>
                                <div className="prefs-form-group">
                                    <label>
                                        <span className="prefs-label-emoji">⚖️</span>
                                        Weight (kg)
                                    </label>
                                    <input
                                        name="weight_kg"
                                        type="number"
                                        placeholder="e.g., 75"
                                        value={prefs.weight_kg}
                                        onChange={onChange}
                                        className="prefs-input"
                                        min="30"
                                        max="300"
                                    />
                                </div>
                                <div className="prefs-form-group">
                                    <label>
                                        <span className="prefs-label-emoji">👤</span>
                                        Gender
                                    </label>
                                    <select
                                        name="gender"
                                        value={prefs.gender}
                                        onChange={onChange}
                                        className="prefs-select"
                                    >
                                        <option value="">-- select --</option>
                                        <option value="female">👩 Female</option>
                                        <option value="male">👨 Male</option>
                                        <option value="other">🌈 Other</option>
                                    </select>
                                </div>
                                <div className="prefs-form-group">
                                    <label>
                                        <span className="prefs-label-emoji">🎂</span>
                                        Age
                                    </label>
                                    <input
                                        name="age"
                                        type="number"
                                        placeholder="e.g., 28"
                                        value={prefs.age}
                                        onChange={onChange}
                                        className="prefs-input"
                                        min="10"
                                        max="120"
                                    />
                                </div>
                            </div>

                            <div className="prefs-bmr-box">
                                <span className="prefs-preview-label">🔥 Estimated Energy Needs (Mifflin-St Jeor)</span>
                                <div className="prefs-bmr-values">
                                    <span>BMR: <strong>{prefs.bmr != null ? `${prefs.bmr} kcal/day` : "—"}</strong></span>
                                    <span>TDEE: <strong>{prefs.tdee != null ? `${prefs.tdee} kcal/day` : "—"}</strong></span>
                                </div>
                                {prefs.bmr == null && (
                                    <p style={{ color: "#94a3b8", fontSize: 13, marginTop: 6 }}>
                                        Fill in height, weight, age and gender, then save to see your estimate.
                                    </p>
                                )}
                            </div>
                        </div>

                        {/* ─── BLOOD TEST ANALYSIS SECTION ────────── */}
                        <div className="prefs-section">
                            <h3>
                                <span className="prefs-section-emoji">🩸</span>
                                Blood Test Analysis
                            </h3>
                            <p style={{ color: "#94a3b8", fontSize: 14, marginBottom: 16 }}>
                                📸 Upload an image of your blood test results for AI-powered health insights
                            </p>
                            {prefs.bloodTestImage && !imagePreview && (
                                <p style={{ color: "#94a3b8", fontSize: 13, marginBottom: 16 }}>
                                    🔒 A blood test image is on file (encrypted). Upload a new one to replace it.
                                </p>
                            )}
                            <div className="prefs-file-input">
                                <input
                                    id="blood-test-file"
                                    type="file"
                                    accept="image/*"
                                    onChange={onFileChange}
                                />
                                <label htmlFor="blood-test-file" className="prefs-file-label">
                                    <span className="prefs-file-icon">📤</span>
                                    <span>Click or drag your blood test image here</span>
                                </label>
                            </div>

                            {imagePreview && (
                                <div className="prefs-preview-section">
                                    <span className="prefs-preview-label">✅ Image Preview</span>
                                    <img
                                        src={imagePreview}
                                        alt="blood-test-preview"
                                        className="prefs-preview-img"
                                    />
                                </div>
                            )}
                        </div>

                        {/* ─── ACTION BUTTONS ────────────────────── */}
                        <div className="prefs-button-group">
                            <button
                                type="submit"
                                className="prefs-btn prefs-btn-save"
                                disabled={loading}
                            >
                                {loading ? "💾 Saving..." : "💚 Save My Preferences"}
                            </button>
                            <button
                                type="button"
                                className="prefs-btn prefs-btn-analyze"
                                onClick={onAnalyze}
                                disabled={loading}
                            >
                                {loading ? "🔄 Analyzing..." : "🧠 Analyze with AI"}
                            </button>
                        </div>
                    </form>

                    {/* ─── AI ANALYSIS RESULT ────────────────── */}
                    {analysis && (
                        <div className="prefs-analysis-box">
                            <div className="prefs-analysis-title">
                                <span>🎯</span>
                                <span>AI Health Insights</span>
                            </div>
                            <div className="prefs-analysis-content">
                                {analysis}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}



