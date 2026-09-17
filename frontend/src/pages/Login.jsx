import { Navigate, useLocation } from "react-router-dom";
import { BookOpen } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

export default function Login() {
  const { user } = useAuth();
  const location = useLocation();
  const from = location.state?.from?.pathname || "/dashboard";
  let hasPendingStory = false;
  try { hasPendingStory = Boolean(localStorage.getItem("idsb_pending_story")); } catch { hasPendingStory = false; }
  if (user) return <Navigate to={from} replace />;

  const handleGoogleLogin = () => {
    const redirectUrl = window.location.origin + "/dashboard";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div className="login-page">
      <div className="auth-card" data-testid="login-card">
        <div className="auth-brand"><span className="auth-brand-mark"><BookOpen size={18} /></span>ID<b style={{ color: "var(--purple)" }}>Storybook</b></div>
        <h1>{hasPendingStory ? "Almost there!" : "Welcome back"}</h1>
        <p>{hasPendingStory
          ? "Your book details are saved. Sign in and we'll start creating it right away — it'll appear in your library."
          : "Sign in to create stories, view your little library, and track your printed books."}</p>
        <button className="btn-google" onClick={handleGoogleLogin} data-testid="google-signin-button">
          <svg width="18" height="18" viewBox="0 0 48 48"><path fill="#FFC107" d="M43.6 20.1H42V20H24v8h11.3C33.7 32.7 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.1 7.9 3l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.7-.4-3.9z" /><path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 16.1 19 13 24 13c3.1 0 5.8 1.1 7.9 3l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" /><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.3 35.2 26.8 36 24 36c-5.3 0-9.7-3.3-11.3-7.9l-6.5 5C9.6 39.6 16.3 44 24 44z" /><path fill="#1976D2" d="M43.6 20.1H42V20H24v8h11.3c-.8 2.3-2.3 4.2-4.3 5.6l6.2 5.2C36.9 36.4 44 31 44 24c0-1.3-.1-2.7-.4-3.9z" /></svg>
          Continue with Google
        </button>
        <p className="auth-note">New here? Your account is created automatically the first time you sign in.</p>
      </div>
    </div>
  );
}
