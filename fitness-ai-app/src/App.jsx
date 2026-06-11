import { Navigate, Route, Routes } from "react-router-dom";
import Home from "./Home";
import Trainings from "./Trainings";
import MyPlan from "./MyPlan.jsx";
import AuthPage from "./AuthPage.jsx";
import ScheduleRecommendations from "./ScheduleRecommendations.jsx";
import GarminDashboard from "./GarminDashboard.jsx";
import Preferences from "./Preferences.jsx";

function App() {
    return (
        <div className="app">
            <Routes>
                <Route path="/" element={<Home />} />
                <Route path="/login" element={<AuthPage mode="login" />} />
                <Route path="/register" element={<AuthPage mode="register" />} />
                <Route path="/trainings" element={<Trainings />} />
                <Route path="/my-plan" element={<MyPlan />} />
                <Route path="/preferences" element={<Preferences />} />
                <Route path="/schedule" element={<ScheduleRecommendations />} />
                <Route path="/garmin" element={<GarminDashboard />} />
                <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
        </div>
    );
}

export default App;