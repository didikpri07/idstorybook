import { useRef, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { BookOpen, Check, Languages, LayoutDashboard, LogOut, Package } from "lucide-react";
import { languages, useLanguage } from "@/i18n";
import { useAuth } from "@/context/AuthContext";

function LanguagePanel({ language, setLanguage, text }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="language-wrap">
      <button className="help-btn language-trigger" onClick={() => setOpen(!open)} aria-label={text.choose} data-testid="language-menu-button">
        <Languages size={18} />
      </button>
      {open && (
        <div className="language-panel" data-testid="language-panel">
          <b>{text.language}</b>
          <small>{text.interface}</small>
          {languages.map(item => (
            <button
              className={language === item.code ? "selected-language" : ""}
              onClick={() => { setLanguage(item.code); setOpen(false); }}
              key={item.code}
              data-testid={`interface-language-${item.code}`}
            >
              {item.flag} {item.label}{language === item.code && <Check size={14} />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function UserMenu({ user, logout, text }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    const close = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  return (
    <div className="user-menu" ref={ref}>
      <button className="user-chip" onClick={() => setOpen(o => !o)} data-testid="user-menu-button">
        {user.picture
          ? <img src={user.picture} alt={user.name} className="user-avatar" referrerPolicy="no-referrer" />
          : <span className="user-avatar-fallback">{(user.name || user.email || "U")[0].toUpperCase()}</span>}
        <span>{user.name?.split(" ")[0] || "Me"}</span>
        {user.role === "admin" && <span className="admin-role-badge" data-testid="admin-badge">Admin</span>}
      </button>
      {open && (
        <div className="user-menu-drop" data-testid="user-dropdown">
          <div className="user-menu-email">{user.email}</div>
          <button onClick={() => { logout(); setOpen(false); }} data-testid="logout-button">
            <LogOut size={15} /> {text.signOut}
          </button>
        </div>
      )}
    </div>
  );
}

export function Shell({ children }) {
  const { language, setLanguage, text } = useLanguage();
  const { user, loading, logout } = useAuth();
  const navigate = useNavigate();
  return (
    <div className="app-shell">
      <header className="topbar">
        <Link to="/" className="brand" data-testid="brand-home">
          <span className="brand-mark"><BookOpen size={19} /></span>
          <span>ID<b>Storybook</b></span>
        </Link>
        <nav>
          <Link to="/dashboard" data-testid="nav-dashboard"><LayoutDashboard size={16} /> {text.library}</Link>
          <Link to="/dashboard#orders" data-testid="nav-orders"><Package size={16} /> {text.orders}</Link>
        </nav>
        <div className="topbar-right">
          <LanguagePanel language={language} setLanguage={setLanguage} text={text} />
          {!loading && (user
            ? <UserMenu user={user} logout={logout} text={text} />
            : <button className="nav-signin" onClick={() => navigate("/login")} data-testid="nav-signin-button">{text.signIn}</button>
          )}
        </div>
      </header>
      {children}
    </div>
  );
}
