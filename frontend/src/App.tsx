import { Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./components/AuthProvider";
import { SettingsProvider } from "./components/SettingsProvider";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import CommandCenter from "./pages/CommandCenter";
import AutomationsPage from "./pages/Automations";
import CalendarPage from "./pages/Calendar";
import TasksPage from "./pages/Tasks";
import PlannerPage from "./pages/Planner";
import ApprovalsPage from "./pages/Approvals";
import ActivityPage from "./pages/Activity";
import SettingsPage from "./pages/Settings";
import LoginPage from "./pages/Login";
import NotFound from "./pages/NotFound";

function WorkspaceRoutes() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/command" element={<CommandCenter />} />
        <Route path="/automations" element={<AutomationsPage />} />
        <Route path="/calendar" element={<CalendarPage />} />
        <Route path="/tasks" element={<TasksPage />} />
        <Route path="/planner" element={<PlannerPage />} />
        <Route path="/approvals" element={<ApprovalsPage />} />
        <Route path="/activity" element={<ActivityPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}

function AuthGate() {
  const { status } = useAuth();

  if (!status) return <LoginPage />;
  if (!status.authenticated) return <LoginPage />;

  return (
    <SettingsProvider>
      <WorkspaceRoutes />
    </SettingsProvider>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AuthGate />
    </AuthProvider>
  );
}
