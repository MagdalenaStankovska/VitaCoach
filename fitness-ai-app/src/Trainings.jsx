import { useEffect, useState } from "react";
import Navbar from "./Navbar.jsx";
import "./Trainings.css";

export default function Trainings() {
    const [selectedProgram, setSelectedProgram] = useState(null);

    const programs = [
        {
            id: "weight-loss-4w",
            title: "Weight Loss in 1 Month",
            duration: "4 weeks",
            level: "Beginner",
            frequency: "5 days/week",
            description: "A fat-loss focused plan that combines cardio intervals and strength sessions to keep metabolism high.",
            highlights: ["Low-impact cardio start", "Core activation daily", "Simple nutrition checkpoints"],
            program: [
                { week: "Week 1", focus: "Build consistency", sessions: ["30 min brisk walk + mobility", "Full body bodyweight circuit", "Steady cardio (bike or jog)"] },
                { week: "Week 2", focus: "Increase calorie burn", sessions: ["Interval cardio 20-25 min", "Lower body strength + core", "Upper body strength + core"] },
                { week: "Week 3", focus: "Conditioning", sessions: ["HIIT lite 18-22 min", "Full body dumbbell session", "Long cardio 40 min"] },
                { week: "Week 4", focus: "Finish strong", sessions: ["Mixed cardio intervals", "Strength + metabolic finisher", "Recovery walk + deep stretch"] }
            ]
        },
        {
            id: "abs-8w",
            title: "Build Abs in 8 Weeks",
            duration: "8 weeks",
            level: "Intermediate",
            frequency: "6 days/week",
            description: "Progressive core training with strategic strength and cardio to reveal abs while improving trunk stability.",
            highlights: ["Progressive core overload", "Anti-rotation training", "Fat-loss support conditioning"],
            program: [
                { week: "Weeks 1-2", focus: "Core foundation", sessions: ["Plank variations + dead bug", "Upper strength + core superset", "Zone 2 cardio 30 min"] },
                { week: "Weeks 3-4", focus: "Volume progression", sessions: ["Hanging knee raises + cable crunch", "Lower strength + loaded carries", "Tempo run or cycling"] },
                { week: "Weeks 5-6", focus: "Definition phase", sessions: ["Ab circuit (3 rounds)", "Push/Pull strength split", "HIIT core finisher"] },
                { week: "Weeks 7-8", focus: "Peak and maintain", sessions: ["Weighted abs day", "Athletic core + conditioning", "Deload mobility + control work"] }
            ]
        },
        {
            id: "glutes-3w",
            title: "Stronger Glutes in 3 Weeks",
            duration: "3 weeks",
            level: "All levels",
            frequency: "4 days/week",
            description: "A short, focused glute strength block with activation, heavy patterns, and recovery to improve shape and power.",
            highlights: ["Hip thrust progression", "Glute medius stability", "Lower-back friendly sequencing"],
            program: [
                { week: "Week 1", focus: "Activation and form", sessions: ["Band activation sequence", "Hip thrust + goblet squat", "Single-leg balance drills"] },
                { week: "Week 2", focus: "Strength overload", sessions: ["Barbell hip thrust focus", "Romanian deadlift + reverse lunge", "Glute bridge burnout"] },
                { week: "Week 3", focus: "Power and symmetry", sessions: ["Step-up + kickback pairing", "Heavy thrust top set + drop sets", "Mobility and recovery flow"] }
            ]
        },
        {
            id: "lean-muscle-6w",
            title: "Lean Muscle in 6 Weeks",
            duration: "6 weeks",
            level: "Intermediate",
            frequency: "5 days/week",
            description: "A hypertrophy-first plan with strategic rest and tempo control to add muscle without excess fat gain.",
            highlights: ["Push/Pull/Leg split", "Volume progression", "Weekly performance checks"],
            program: [
                { week: "Weeks 1-2", focus: "Base hypertrophy", sessions: ["Push day (compound focus)", "Pull day + posterior chain", "Leg day + core"] },
                { week: "Weeks 3-4", focus: "Volume increase", sessions: ["Add one set to key lifts", "Tempo accessories", "Cardio recovery 2x/week"] },
                { week: "Weeks 5-6", focus: "Intensity block", sessions: ["Top sets + backoff sets", "Mechanical drop sets", "Deload finish"] }
            ]
        },
        {
            id: "posture-4w",
            title: "Fix Posture in 4 Weeks",
            duration: "4 weeks",
            level: "Beginner",
            frequency: "4 days/week",
            description: "Desk-worker friendly routine to open chest, strengthen back, and improve spinal alignment.",
            highlights: ["Mobility first", "Upper-back strengthening", "Core and breathing resets"],
            program: [
                { week: "Week 1", focus: "Mobility reset", sessions: ["Thoracic opener flow", "Band pull-aparts", "Breathing + plank"] },
                { week: "Week 2", focus: "Scapular control", sessions: ["Row variations", "Face pulls", "Dead bug progressions"] },
                { week: "Week 3", focus: "Strength integration", sessions: ["Split squat + row", "Reverse fly circuit", "Farmer carry"] },
                { week: "Week 4", focus: "Daily durability", sessions: ["Posture combo circuit", "Core anti-rotation", "Maintenance template"] }
            ]
        },
        {
            id: "runner-5k-6w",
            title: "Run Your First 5K in 6 Weeks",
            duration: "6 weeks",
            level: "Beginner",
            frequency: "4 days/week",
            description: "A walk-run progression that builds endurance safely while improving pace and breathing control.",
            highlights: ["Gradual load", "Speed intro", "Injury-prevention mobility"],
            program: [
                { week: "Weeks 1-2", focus: "Walk-run base", sessions: ["Intervals: 2 min run / 2 min walk", "Easy cross-training", "Lower body mobility"] },
                { week: "Weeks 3-4", focus: "Endurance growth", sessions: ["Intervals: 4 min run / 1 min walk", "Tempo intro day", "Core stability"] },
                { week: "Weeks 5-6", focus: "Race readiness", sessions: ["Continuous run progression", "5K pace rehearsal", "Recovery walk + stretch"] }
            ]
        },
        {
            id: "home-tone-4w",
            title: "Home Body Toning in 4 Weeks",
            duration: "4 weeks",
            level: "All levels",
            frequency: "5 days/week",
            description: "No-gym required program using bodyweight and light dumbbells for full-body toning.",
            highlights: ["Minimal equipment", "Short efficient sessions", "Balanced upper/lower/core work"],
            program: [
                { week: "Week 1", focus: "Movement quality", sessions: ["Bodyweight full-body A", "Core + mobility", "Bodyweight full-body B"] },
                { week: "Week 2", focus: "Add resistance", sessions: ["Dumbbell circuit", "Lower body burn", "Upper body + core"] },
                { week: "Week 3", focus: "Density", sessions: ["EMOM conditioning", "Glute and leg focus", "Push/Pull supersets"] },
                { week: "Week 4", focus: "Refine and repeat", sessions: ["AMRAP full body", "Mobility reset", "Final challenge session"] }
            ]
        },
        {
            id: "strength-beginner-5w",
            title: "Beginner Strength Reset in 5 Weeks",
            duration: "5 weeks",
            level: "Beginner",
            frequency: "4 days/week",
            description: "A confidence-building strength block to teach core movement patterns and build steady progress.",
            highlights: ["Squat/push/hinge basics", "Simple progression", "Recovery-friendly split"],
            program: [
                { week: "Week 1", focus: "Pattern foundations", sessions: ["Goblet squat + press", "Row + hip hinge", "Mobility and walking"] },
                { week: "Week 2", focus: "Tempo and control", sessions: ["Tempo squats", "Incline push-ups", "Light conditioning"] },
                { week: "Week 3", focus: "Progressive loading", sessions: ["Dumbbell full-body A", "Dumbbell full-body B", "Core bracing drills"] },
                { week: "Week 4", focus: "Strength confidence", sessions: ["Circuit strength day", "Single-leg balance work", "Carry finisher"] },
                { week: "Week 5", focus: "Benchmark and deload", sessions: ["Performance check", "Technique tune-up", "Mobility deload"] }
            ]
        },
        {
            id: "mobility-flow-3w",
            title: "Mobility Flow and Recovery in 3 Weeks",
            duration: "3 weeks",
            level: "All levels",
            frequency: "6 days/week",
            description: "A recovery-first plan to open hips and shoulders, reduce stiffness, and improve movement quality.",
            highlights: ["Daily 15-20 min flows", "Hip and thoracic focus", "Great between hard blocks"],
            program: [
                { week: "Week 1", focus: "Open the body", sessions: ["Hip opener flow", "Thoracic rotation sequence", "Ankle and calf mobility"] },
                { week: "Week 2", focus: "Control end ranges", sessions: ["Shoulder CARs + band work", "Cossack squat mobility", "Core breathing reset"] },
                { week: "Week 3", focus: "Move better daily", sessions: ["Full-body recovery flow", "Yoga-inspired balance work", "Long stretch and unwind"] }
            ]
        }
    ];

    useEffect(() => {
        const closeOnEscape = (event) => {
            if (event.key === "Escape") {
                setSelectedProgram(null);
            }
        };

        window.addEventListener("keydown", closeOnEscape);
        return () => window.removeEventListener("keydown", closeOnEscape);
    }, []);

    return (
        <div className="app">
            <Navbar />

            <div className="hero">
                <h1>Popular Trainings</h1>
                <p>Pick a proven transformation goal and start your guided plan</p>
            </div>

            <div className="training-wrapper">
                <div className="training-grid">
                    {programs.map((program) => (
                        <article key={program.id} className="training-card">
                            <div className="training-chip-row">
                                <span className="training-chip training-chip-duration">{program.duration}</span>
                                <span className="training-chip training-chip-level">{program.level}</span>
                            </div>

                            <h3>{program.title}</h3>
                            <p>{program.description}</p>

                            <ul className="training-highlights">
                                {program.highlights.map((point) => (
                                    <li key={point}>{point}</li>
                                ))}
                            </ul>

                            <button
                                type="button"
                                className="save-btn training-start-btn"
                                onClick={() => setSelectedProgram(program)}
                            >
                                Start Training
                            </button>
                        </article>
                    ))}
                </div>
            </div>

            {selectedProgram && (
                <div className="training-modal-overlay" onClick={() => setSelectedProgram(null)}>
                    <div className="training-modal" onClick={(event) => event.stopPropagation()}>
                        <button
                            type="button"
                            className="training-modal-close"
                            onClick={() => setSelectedProgram(null)}
                            aria-label="Close training details"
                        >
                            x
                        </button>

                        <h2>{selectedProgram.title}</h2>

                        <div className="training-modal-meta">
                            <span>{selectedProgram.duration}</span>
                            <span>{selectedProgram.level}</span>
                            <span>{selectedProgram.frequency}</span>
                        </div>

                        <p className="training-modal-description">{selectedProgram.description}</p>

                        <div className="training-modal-program">
                            {selectedProgram.program.map((block) => (
                                <section key={block.week} className="training-week-card">
                                    <h4>{block.week}</h4>
                                    <p>{block.focus}</p>
                                    <ul>
                                        {block.sessions.map((session) => (
                                            <li key={session}>{session}</li>
                                        ))}
                                    </ul>
                                </section>
                            ))}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}