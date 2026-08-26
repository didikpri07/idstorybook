import { Link, Navigate, useLocation } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { Shell } from "@/components/Shell";

export function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return (
    <div className="app-shell">
      <div className="center-page">
        <span className="spinner" style={{ border: "2px solid #ddd9e8", borderTopColor: "var(--purple)", width: 28, height: 28 }} />
      </div>
    </div>
  );
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  return children;
}

export function AdminRoute({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return (
    <div className="app-shell">
      <div className="center-page">
        <span className="spinner" style={{ border: "2px solid #ddd9e8", borderTopColor: "var(--purple)", width: 28, height: 28 }} />
      </div>
    </div>
  );
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  if (user.role !== "admin") return (
    <Shell>
      <div className="center-page" data-testid="access-denied-page">
        <div className="success-icon" style={{ background: "#f1f0f7" }}>🔒</div>
        <div className="eyebrow">Restricted area</div>
        <h1 style={{ fontSize: "2rem" }}>Access Denied</h1>
        <p className="center-sub">
          This page is only available to admins.<br />Signed in as <b>{user.email}</b>.
        </p>
        <Link to="/dashboard" className="btn btn-primary" data-testid="back-to-dashboard-link">
          Go to my dashboard <ArrowRight size={17} />
        </Link>
      </div>
    </Shell>
  );
  return children;
}
