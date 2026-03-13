import { Routes, Route } from "react-router-dom";
import Navbar from "./Navbar";
import Home from "./Home";
import Trainings from "./Trainings";
import MyPlan from "./MyPlan.jsx";

function App() {
    return (
        <div className="app">


            <Routes>
                <Route path="/" element={<Home />} />
                <Route path="/trainings" element={<Trainings />} />
                <Route path="/my-plan" element={<MyPlan />} />
            </Routes>
        </div>
    );
}

export default App;