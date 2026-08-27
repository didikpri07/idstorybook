import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { BookOpen } from "lucide-react";
import axios from "axios";
import { useAuth } from "@/context/AuthContext";
import { API } from "@/lib/constants";

export default function AuthCallback() {
  const navigate = useNavigate();
  const location = useLocation();
  const { setUser } = useAuth();
  const hasProcessed = useRef(false);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const match = location.hash?.match(/session_id=([^&]+)/);
    if (!match) { navigate("/"); return; }

    const sessionId = decodeURIComponent(match[1]);
    axios.post(`${API}/auth/session`, { session_id: sessionId }, { withCredentials: true })
      .then(({ data }) => { setUser(data.user); navigate(data.user?.role === "admin" ? "/admin" : "/dashboard", { replace: true }); })
      .catch(() => navigate("/login", { replace: true }));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="login-page">
      <div className="auth-card">
        <div className="auth-brand"><span className="auth-brand-mark"><BookOpen size={18} /></span>ID<b style={{ color: "var(--purple)" }}>Storybook</b></div>
        <span className="spinner" style={{ border: "2px solid #e2e0ee", borderTopColor: "var(--purple)", width: 36, height: 36, margin: "16px auto" }} />
        <p>Signing you in…</p>
      </div>
    </div>
  );
}
