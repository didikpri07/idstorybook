import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import "@/App.css";
import "@/Language.css";
import { BrowserRouter, Navigate, Route, Routes, Link, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import axios from "axios";
import { ArrowRight, BookOpen, Box, Check, ChevronLeft, ChevronRight, CloudUpload, Crown, Heart, Languages, LayoutDashboard, LogOut, Package, Pause, Play, Sparkles, User, Volume2, VolumeX, WandSparkles } from "lucide-react";
import { copy, languages, useLanguage } from "@/i18n";

// --- Constants ---
const MIDTRANS_CLIENT_KEY = process.env.REACT_APP_MIDTRANS_CLIENT_KEY || "";
const MIDTRANS_IS_PRODUCTION = process.env.REACT_APP_MIDTRANS_IS_PRODUCTION === "true";
const BOOK_PRICES = { Hardcover: { usd: "$34.00", idr: "Rp 549.000" }, Softcover: { usd: "$22.00", idr: "Rp 359.000" } };
const COUNTRIES = ["Australia", "Canada", "Germany", "Indonesia", "Malaysia", "Netherlands", "New Zealand", "Philippines", "Singapore", "United Kingdom", "United States", "Other"];
const BACKEND = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND}/api`;
const resolveImage = src => (src && src.startsWith("/api/") ? `${BACKEND}${src}` : src);
const themes = [{ name: "Moonlit Forest", id: "Hutan Cahaya Bulan", icon: "✦", color: "lavender" }, { name: "Ocean Explorer", id: "Penjelajah Laut", icon: "≈", color: "blue" }, { name: "Dinosaur Valley", id: "Lembah Dinosaurus", icon: "◈", color: "coral" }];
const storyLanguages = [{ code: "en", label: "English", flag: "🇬🇧" }, { code: "id", label: "Bahasa Indonesia", flag: "🇮🇩" }];
function languageLabel(theme) { return window.localStorage.getItem("kids-storybook-ui") === "id" ? theme.id : theme.name; }

const COVER_THEMES = {
  "Moonlit Forest":  { bg: "linear-gradient(155deg,#0f0c29 0%,#302b63 55%,#1a3a2a 100%)", spine: "#09071c", accent: "#c4b5fd", star: "✦", emoji: "🌙" },
  "Ocean Explorer":  { bg: "linear-gradient(155deg,#0c4a6e 0%,#0284c7 55%,#0e7490 100%)", spine: "#082e45", accent: "#7dd3fc", star: "≈", emoji: "🌊" },
  "Dinosaur Valley": { bg: "linear-gradient(155deg,#14532d 0%,#15803d 55%,#713f12 100%)", spine: "#0a321b", accent: "#86efac", star: "◈", emoji: "🦕" },
};

function CoverPreview({ childName, theme, photoBase64 }) {
  const t = COVER_THEMES[theme] || COVER_THEMES["Moonlit Forest"];
  const name = childName?.trim() || "Your Child";
  return (
    <div className="cover-preview-wrap" data-testid="cover-preview">
      <div className="cover-3d">
        <div className="book-spine" style={{ background: t.spine }}>
          <span>{name[0]?.toUpperCase() || "?"}</span>
        </div>
        <div className="book-face" style={{ background: t.bg }}>
          <div className="cover-deco" style={{ color: t.accent }}>{t.star} {t.emoji} {t.star}</div>
          {photoBase64
            ? <div className="cover-photo-ring" style={{ borderColor: t.accent }}><img src={photoBase64} alt="Child" className="cover-photo-img" /></div>
            : <div className="cover-photo-ring cover-photo-empty" style={{ borderColor: t.accent, color: t.accent }}><User size={28} /></div>
          }
          <div className="cover-child-name" style={{ color: t.accent }} data-testid="cover-child-name">{name}</div>
          <div className="cover-tagline">& the {theme}</div>
          <div className="cover-brand-label">Kids Storybook</div>
        </div>
      </div>
      <p className="cover-caption">Live cover preview · updates as you type</p>
    </div>
  );
}

function loadMidtransSnap() {
  return new Promise((resolve, reject) => {
    if (window.snap) { resolve(window.snap); return; }
    const existing = document.getElementById("midtrans-snap-js");
    if (existing) { existing.onload = () => resolve(window.snap); return; }
    const s = document.createElement("script");
    s.id = "midtrans-snap-js";
    s.src = MIDTRANS_IS_PRODUCTION ? "https://app.midtrans.com/snap/snap.js" : "https://app.sandbox.midtrans.com/snap/snap.js";
    s.setAttribute("data-client-key", MIDTRANS_CLIENT_KEY);
    s.onload = () => resolve(window.snap);
    s.onerror = reject;
    document.head.appendChild(s);
  });
}

// ---------- Auth context ----------
const AuthContext = createContext(null);

function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const checkAuth = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/auth/me`, { withCredentials: true });
      setUser(data);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // CRITICAL: If returning from OAuth callback, skip the /me check.
    // AuthCallback will exchange the session_id and establish the session first.
    if (window.location.hash?.includes("session_id=")) { setLoading(false); return; }
    checkAuth();
  }, [checkAuth]);

  const logout = useCallback(async () => {
    await axios.post(`${API}/auth/logout`, {}, { withCredentials: true }).catch(() => {});
    setUser(null);
  }, []);

  return <AuthContext.Provider value={{ user, loading, setUser, logout }}>{children}</AuthContext.Provider>;
}

function useAuth() { return useContext(AuthContext); }

// ---------- Language panel ----------
function LanguagePanel({ language, setLanguage, text }) {
  const [open, setOpen] = useState(false);
  return <div className="language-wrap"><button className="help-btn language-trigger" onClick={() => setOpen(!open)} aria-label={text.choose} data-testid="language-menu-button"><Languages size={18} /></button>{open && <div className="language-panel" data-testid="language-panel"><b>{text.language}</b><small>{text.interface}</small>{languages.map(item => <button className={language === item.code ? "selected-language" : ""} onClick={() => { setLanguage(item.code); setOpen(false); }} key={item.code} data-testid={`interface-language-${item.code}`}>{item.flag} {item.label}{language === item.code && <Check size={14} />}</button>)}</div>}</div>;
}

// ---------- Shell / nav ----------
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
        {user.picture ? <img src={user.picture} alt={user.name} className="user-avatar" referrerPolicy="no-referrer" /> : <span className="user-avatar-fallback">{(user.name || user.email || "U")[0].toUpperCase()}</span>}
        <span>{user.name?.split(" ")[0] || "Me"}</span>
        {user.role === "admin" && <span className="admin-role-badge" data-testid="admin-badge">Admin</span>}
      </button>
      {open && (
        <div className="user-menu-drop" data-testid="user-dropdown">
          <div className="user-menu-email">{user.email}</div>
          <button onClick={() => { logout(); setOpen(false); }} data-testid="logout-button"><LogOut size={15} /> {text.signOut}</button>
        </div>
      )}
    </div>
  );
}

function Shell({ children }) {
  const { language, setLanguage, text } = useLanguage();
  const { user, loading, logout } = useAuth();
  const navigate = useNavigate();
  return (
    <div className="app-shell">
      <header className="topbar">
        <Link to="/" className="brand" data-testid="brand-home"><span className="brand-mark"><BookOpen size={19} /></span><span>Kids <b>Storybook</b></span></Link>
        <nav>
          <Link to="/dashboard" data-testid="nav-dashboard"><LayoutDashboard size={16} /> {text.library}</Link>
          <Link to="/admin" data-testid="nav-admin"><Package size={16} /> {text.orders}</Link>
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

// ---------- Auth components ----------
function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div className="app-shell"><div className="center-page"><span className="spinner" style={{ border: "2px solid #ddd9e8", borderTopColor: "var(--purple)", width: 28, height: 28 }} /></div></div>;
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  return children;
}

function AdminRoute({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div className="app-shell"><div className="center-page"><span className="spinner" style={{ border: "2px solid #ddd9e8", borderTopColor: "var(--purple)", width: 28, height: 28 }} /></div></div>;
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  if (user.role !== "admin") return <Shell><div className="center-page" data-testid="access-denied-page">
    <div className="success-icon" style={{ background: "#f1f0f7" }}>🔒</div>
    <div className="eyebrow">Restricted area</div>
    <h1 style={{ fontSize: "2rem" }}>Access Denied</h1>
    <p className="center-sub">This page is only available to admins.<br />Signed in as <b>{user.email}</b>.</p>
    <Link to="/dashboard" className="btn btn-primary" data-testid="back-to-dashboard-link">Go to my dashboard <ArrowRight size={17} /></Link>
  </div></Shell>;
  return children;
}

function AuthCallback() {
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
      .then(({ data }) => { setUser(data.user); navigate("/dashboard", { replace: true }); })
      .catch(() => navigate("/login", { replace: true }));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="login-page">
      <div className="auth-card">
        <div className="auth-brand"><span className="auth-brand-mark"><BookOpen size={18} /></span>Kids <b style={{ color: "var(--purple)" }}>Storybook</b></div>
        <span className="spinner" style={{ border: "2px solid #e2e0ee", borderTopColor: "var(--purple)", width: 36, height: 36, margin: "16px auto" }} />
        <p>Signing you in…</p>
      </div>
    </div>
  );
}

function Login() {
  const { user } = useAuth();
  const location = useLocation();
  const from = location.state?.from?.pathname || "/dashboard";
  if (user) return <Navigate to={from} replace />;

  const handleGoogleLogin = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + "/dashboard";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div className="login-page">
      <div className="auth-card" data-testid="login-card">
        <div className="auth-brand"><span className="auth-brand-mark"><BookOpen size={18} /></span>Kids <b style={{ color: "var(--purple)" }}>Storybook</b></div>
        <h1>Welcome back</h1>
        <p>Sign in to create stories, view your little library, and track your printed books.</p>
        <button className="btn-google" onClick={handleGoogleLogin} data-testid="google-signin-button">
          <svg width="18" height="18" viewBox="0 0 48 48"><path fill="#FFC107" d="M43.6 20.1H42V20H24v8h11.3C33.7 32.7 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.1 7.9 3l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.7-.4-3.9z" /><path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 16.1 19 13 24 13c3.1 0 5.8 1.1 7.9 3l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" /><path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.3 35.2 26.8 36 24 36c-5.3 0-9.7-3.3-11.3-7.9l-6.5 5C9.6 39.6 16.3 44 24 44z" /><path fill="#1976D2" d="M43.6 20.1H42V20H24v8h11.3c-.8 2.3-2.3 4.2-4.3 5.6l6.2 5.2C36.9 36.4 44 31 44 24c0-1.3-.1-2.7-.4-3.9z" /></svg>
          Continue with Google
        </button>
        <p className="auth-note">New here? Your account is created automatically the first time you sign in.</p>
      </div>
    </div>
  );
}

// ---------- App pages ----------
function SamplePeek() {
  const { text } = useLanguage();
  const [story, setStory] = useState(null);
  const [idx, setIdx] = useState(0);
  const [tick, setTick] = useState(0);
  useEffect(() => { axios.get(`${API}/stories/${encodeURIComponent("narrator-demo-01")}`).then(response => setStory(response.data)).catch(() => setStory(null)); }, []);
  useEffect(() => {
    if (!story || !story.pages || story.pages.length < 2) return;
    const timer = setInterval(() => setIdx(previous => (previous + 1) % story.pages.length), 4200);
    return () => clearInterval(timer);
  }, [story, tick]);
  if (!story || !story.pages || !story.pages.length) return null;
  const page = story.pages[idx];
  const selectPage = i => { setIdx(i); setTick(previous => previous + 1); };
  return <section className="sample" data-testid="sample-peek-section">
    <div className="sample-visual">
      <img src={resolveImage(page.image)} alt="Sample story illustration" data-testid="sample-illustration" />
      <span className="sample-page-badge">{text.samplePage} {idx + 1} / {story.pages.length}</span>
      <span className="sample-narrator-chip"><Volume2 size={13} /> {text.sampleNarrated} · {story.narrator_voice || "nova"}</span>
    </div>
    <div className="sample-body">
      <div className="eyebrow"><Sparkles size={13} /> {text.sampleEyebrow}</div>
      <h2 className="sample-title">{text.sampleTitleA}<br /><em>{text.sampleTitleB}</em></h2>
      <p className="sample-description">{text.sampleDescription}</p>
      <p className="sample-preview" key={idx} data-testid="sample-preview-text">"{page.text}"</p>
      <div className="sample-dots" data-testid="sample-dots">
        {story.pages.map((_, i) => <button key={i} type="button" aria-label={`${text.samplePage} ${i + 1}`} className={i === idx ? "selected" : ""} onClick={() => selectPage(i)} data-testid={`sample-dot-${i}`}><span /></button>)}
      </div>
      <Link to={`/storybook/${story.id}`} className="btn btn-primary sample-cta" data-testid="sample-peek-cta">{text.sampleCta} <ArrowRight size={17} /></Link>
    </div>
  </section>;
}

function Home() {
  const { text } = useLanguage();
  return <Shell><main className="hero">
    <div className="hero-copy">
      <div className="eyebrow"><Sparkles size={15} /> {text.homeEyebrow}</div>
      <h1>{text.homeTitleA}<br /><em>{text.homeTitleB}</em></h1>
      <p>{text.homeDescription}</p>
      <div className="hero-actions">
        <Link to="/create" className="btn btn-primary" data-testid="create-book-button">{text.createBook} <ArrowRight size={17} /></Link>
        <Link to="/dashboard" className="text-link" data-testid="view-library-link">{text.viewLibrary} <BookOpen size={16} /></Link>
      </div>
      <div className="trust"><div className="avatar-stack"><span>🌟</span><span>🦊</span><span>🌈</span><span>+</span></div><span>{text.loved}</span></div>
    </div>
    <div className="hero-art">
      <div className="sun" />
      <div className="art-label">A story starring your little one</div>
      <img src="https://images.unsplash.com/photo-1645113614899-000bdab2bbcf?crop=entropy&cs=srgb&fm=jpg&q=85" alt="Whimsical storybook scene" data-testid="hero-image" />
      <div className="floating-note note-one">✦ <b>{text.madeWonder}</b></div>
      <div className="floating-note note-two">☼ {text.printed}</div>
    </div>
  </main>
  <SamplePeek />
  <section className="theme-strip">
    <div><span className="section-kicker">Pick Their Story World</span><h2>{text.whereGo}</h2></div>
    <div className="theme-cards">
      {themes.map(theme => <div className={`theme-card ${theme.color}`} key={theme.name} data-testid={`theme-card-${theme.name.toLowerCase().replaceAll(" ", "-")}`}><span>{theme.icon}</span><b>{languageLabel(theme)}</b><small>{text.buildStory}</small></div>)}
    </div>
  </section></Shell>;
}

function Create() {
  const { language, text } = useLanguage();
  const [form, setForm] = useState({ child_name: "", age: 5, gender: "", theme: "Moonlit Forest", photo_base64: "", story_language: "en" });
  const [photoName, setPhotoName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState("");
  const update = event => setForm({ ...form, [event.target.name]: event.target.value });
  const readAsDataUrl = file => new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = reject; reader.readAsDataURL(file); });
  const onPhoto = async event => { const file = event.target.files?.[0]; if (!file) return; setPhotoName(file.name); const dataUrl = await readAsDataUrl(file); setForm(previous => ({ ...previous, photo_base64: dataUrl })); };
  const submit = async event => {
    event.preventDefault(); setLoading(true); setError("");
    try {
      const response = await axios.post(`${API}/stories`, form, { timeout: 180000, withCredentials: true });
      setPreview(response.data.id);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(detail || text.createError);
    } finally { setLoading(false); }
  };
  if (preview) return <Shell><div className="center-page"><div className="success-icon"><Check /></div><div className="eyebrow">{text.ready}</div><h1>{text.meet} {form.child_name}'s<br /><em>{text.adventure}</em></h1><p className="center-sub">{text.readyDescription} {form.child_name}.</p><Link to={`/storybook/${preview}`} className="btn btn-primary" data-testid="open-storybook-button">{text.openStory} <ArrowRight size={17} /></Link></div></Shell>;
  return <Shell><main className="create-layout">
    <div className="create-intro">
      <div className="eyebrow"><WandSparkles size={15} /> {text.createEyebrow}</div>
      <h1>{text.createTitleA}<br /><em>{text.createTitleB}</em></h1>
      <p>{text.createDescription}</p>
      <div className="steps"><span className="active">01</span><i /><span>02</span><i /><span>03</span></div>
      <CoverPreview childName={form.child_name} theme={form.theme} photoBase64={form.photo_base64} />
    </div>
    <form className="form-panel" onSubmit={submit}>
      {error && <div className="error-message" role="alert" data-testid="create-error-message">{error}</div>}
      <label>{text.name}<input name="child_name" value={form.child_name} onChange={update} placeholder={language === "id" ? "contoh: Maya" : "e.g. Maya"} required data-testid="child-name-input" /></label>
      <div className="two-col">
        <label>{text.age}<select name="age" value={form.age} onChange={update} data-testid="child-age-select">{[3, 4, 5, 6, 7, 8, 9, 10].map(age => <option key={age}>{age}</option>)}</select></label>
        <label>{text.personality}<select name="gender" value={form.gender} onChange={update} required data-testid="child-gender-select"><option value="">{text.choose}</option><option>{language === "id" ? "Pemberani" : "Adventurous"}</option><option>{language === "id" ? "Penasaran" : "Curious"}</option><option>{language === "id" ? "Imajinatif" : "Imaginative"}</option></select></label>
      </div>
      <label>{text.world}<select name="theme" value={form.theme} onChange={update} data-testid="story-theme-select">{themes.map(theme => <option key={theme.name} value={theme.name}>{language === "id" ? theme.id : theme.name}</option>)}</select></label>
      <label className="upload">{text.photo}
        <div className="upload-box"><CloudUpload size={24} /><span><b>{photoName || text.dropPhoto}</b> {!photoName && text.browse}</span><small>{text.photoHint}</small></div>
        <input type="file" accept="image/*" data-testid="child-photo-input" onChange={onPhoto} />
      </label>
      <div className="story-language-field">
        <label>{text.storybook}<select name="story_language" value={form.story_language} onChange={update} data-testid="storybook-language-select">{storyLanguages.map(item => <option value={item.code} key={item.code}>{item.flag} {item.label}</option>)}</select></label>
        <small>{language === "id" ? "Bahasa ini akan digunakan untuk teks buku cerita." : "This language will be used for the story text."}</small>
      </div>
      <button className="btn btn-primary full" disabled={loading} data-testid="generate-story-button">{loading ? <><span className="spinner" /> {text.weaving}</> : <>{text.magic} <WandSparkles size={17} /></>}</button>
      <small className="safe-note">🔒 {text.privacy}</small>
    </form>
  </main></Shell>;
}

function Storybook() {
  const { text } = useLanguage();
  const { id } = useParams();
  const [story, setStory] = useState(null);
  const [error, setError] = useState("");
  const [page, setPage] = useState(0);
  const [unlocked, setUnlocked] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(false);
  const audioRef = useRef(null);

  useEffect(() => {
    axios.get(`${API}/stories/${id}`).then(response => setStory(response.data)).catch(() => setError(text.storyError));
  }, [id, text.storyError]);

  useEffect(() => {
    if (!unlocked || !story) return;
    const el = audioRef.current;
    if (!el) return;
    el.currentTime = 0;
    el.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
  }, [page, unlocked, story]);

  if (error) return <Shell><div className="center-page"><div className="error-message" role="alert" data-testid="storybook-error-message">{error}</div></div></Shell>;
  if (!story) return <Shell><div className="center-page"><span className="spinner" /><p>{text.storyLoading}</p></div></Shell>;

  const current = story.pages[page];
  const isLast = page === story.pages.length - 1;
  const audioSrc = current.audio ? resolveImage(current.audio) : null;

  const startReading = async () => {
    setUnlocked(true);
    const el = audioRef.current;
    if (el) { try { await el.play(); setPlaying(true); } catch { setPlaying(false); } }
  };
  const togglePlay = async () => {
    const el = audioRef.current;
    if (!el) return;
    if (el.paused) { try { await el.play(); setPlaying(true); } catch { setPlaying(false); } }
    else { el.pause(); setPlaying(false); }
  };
  const toggleMute = () => { setMuted(previous => { const next = !previous; if (audioRef.current) audioRef.current.muted = next; return next; }); };
  const onEnded = () => { setPlaying(false); if (!isLast) setPage(page + 1); };
  const goPage = next => { setPage(next); };

  return <Shell><main className="reader">
    <div className="reader-head">
      <Link to="/dashboard" className="back-link" data-testid="back-library-link"><ChevronLeft size={17} /> {text.backLibrary}</Link>
      <span className="reader-title"><BookOpen size={16} /> {story.title}</span>
      <Link to={`/checkout?story_id=${story.id}&child_name=${encodeURIComponent(story.child_name)}`} className="btn btn-coral" data-testid="order-physical-book-button">{text.orderPhysical} <Box size={16} /></Link>
    </div>
    <div className="book">
      <div className="book-image">
        <img src={resolveImage(current.image)} alt="Story illustration" data-testid="storybook-illustration" />
        <span className="page-number">{page + 1} / {story.pages.length}</span>
      </div>
      <div className="book-text">
        <span className="page-kicker">{text.chapter} {page + 1}</span>
        <p data-testid="storybook-page-text">{current.text}</p>
        {audioSrc ? <audio ref={audioRef} src={audioSrc} preload="auto" onEnded={onEnded} onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} data-testid="narrator-audio" /> : null}
        <div className="narrator-controls" data-testid="narrator-controls">
          {!unlocked && audioSrc ? <button type="button" className="btn btn-primary btn-sm narrator-start" onClick={startReading} data-testid="start-read-aloud-button"><Play size={16} /> {text.readAloud}</button> : null}
          {unlocked && audioSrc ? <>
            <button type="button" className="icon-btn" onClick={togglePlay} aria-label={playing ? text.stopReading : text.readAloud} data-testid="toggle-play-button">{playing ? <Pause size={18} /> : <Play size={18} />}</button>
            <button type="button" className="icon-btn" onClick={toggleMute} aria-label={muted ? text.unmuteNarrator : text.muteNarrator} data-testid="toggle-mute-button">{muted ? <VolumeX size={18} /> : <Volume2 size={18} />}</button>
            <small className="narrator-hint" data-testid="narrator-hint">{playing ? "◆ " + text.readAloud : text.readAloud}</small>
          </> : null}
          {!audioSrc ? <small className="narrator-hint" data-testid="narrator-missing">{text.narrationUnavailable}</small> : null}
        </div>
        <div className="reader-controls">
          <button aria-label={text.previous} onClick={() => goPage(Math.max(0, page - 1))} disabled={!page} data-testid="previous-page-button"><ChevronLeft /></button>
          <div className="dots">{story.pages.map((_, index) => <span className={index === page ? "selected" : ""} key={index} />)}</div>
          <button aria-label={text.next} onClick={() => goPage(Math.min(story.pages.length - 1, page + 1))} disabled={isLast} data-testid="next-page-button"><ChevronRight /></button>
        </div>
      </div>
    </div>
  </main></Shell>;
}

function Checkout() {
  const { text } = useLanguage();
  const [params] = useSearchParams();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [format, setFormat] = useState("Hardcover");
  const [country, setCountry] = useState("Other");
  const [form, setForm] = useState({ customer_name: "", email: "", address: "", city: "", postal_code: "" });
  const update = e => setForm({ ...form, [e.target.name]: e.target.value });
  const isIndonesia = country === "Indonesia";
  const price = BOOK_PRICES[format] || BOOK_PRICES.Hardcover;
  const displayPrice = isIndonesia ? price.idr : price.usd;

  const submit = async e => {
    e.preventDefault(); setError(""); setLoading(true);
    try {
      const payload = { ...form, story_id: params.get("story_id") || "demo", child_name: params.get("child_name") || "Story friend", format, gift_box: false, country, origin_url: window.location.origin };
      const { data } = await axios.post(`${API}/orders`, payload, { timeout: 20000, withCredentials: true });
      if (data.gateway === "stripe") { window.location.href = data.checkout_url; }
      else if (data.gateway === "midtrans") {
        const snap = await loadMidtransSnap();
        setLoading(false);
        snap.pay(data.snap_token, {
          onSuccess: () => { window.location.href = `/checkout/success?order_id=${data.id}`; },
          onPending: () => { window.location.href = `/checkout/success?order_id=${data.id}&pending=1`; },
          onError: () => setError(text.orderError),
          onClose: () => setError(""),
        });
      }
    } catch (err) {
      setError(err?.response?.data?.detail || text.orderError);
      setLoading(false);
    }
  };

  return <Shell><main className="checkout">
    <div className="checkout-title">
      <Link to="/dashboard" className="back-link" data-testid="back-storybook-link"><ChevronLeft size={17} /> {text.checkoutBack}</Link>
      <h1>{text.checkoutTitleA} <em>{text.checkoutTitleB}</em></h1>
      <p>{text.checkoutDescription}</p>
    </div>
    <form className="checkout-form" onSubmit={submit}>
      {error && <div className="error-message" role="alert" data-testid="checkout-error-message">{error}</div>}
      <div className="format-row">
        <h3>{text.cover}</h3>
        <div className="format-options">
          {[["Hardcover", "★★★★★"], ["Softcover", "★★★★☆"]].map(([name, stars]) => {
            const p = BOOK_PRICES[name]; const pr = isIndonesia ? p.idr : p.usd;
            return <button type="button" onClick={() => setFormat(name)} className={`format-option ${format === name ? "chosen" : ""}`} key={name} data-testid={`format-${name.toLowerCase()}-option`}>
              <span className="cover-icon">▣</span>
              <b>{name === "Hardcover" ? text.hardcover : text.softcover}</b>
              <small>{stars} · {pr}</small>
              {format === name && <Check size={16} />}
            </button>;
          })}
        </div>
      </div>
      <div className="field-section">
        <h3>{text.send}</h3>
        <div className="two-col">
          <input name="customer_name" placeholder={text.fullName} required onChange={update} data-testid="shipping-name-input" />
          <input name="email" type="email" placeholder={text.email} required onChange={update} data-testid="shipping-email-input" />
        </div>
        <input name="address" placeholder={text.address} required onChange={update} data-testid="shipping-address-input" />
        <div className="two-col">
          <input name="city" placeholder={text.city} required onChange={update} data-testid="shipping-city-input" />
          <input name="postal_code" placeholder={text.postal} required onChange={update} data-testid="shipping-postal-input" />
        </div>
        <select value={country} onChange={e => setCountry(e.target.value)} required data-testid="shipping-country-select">
          <option value="">{text.selectCountry}</option>
          {COUNTRIES.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>
      <div className="payment-note">
        <Crown size={18} />
        <span><b>{text.secure}</b><small>{text.paymentHint}</small></span>
        <span className="payment-brand">{isIndonesia ? "midtrans" : "stripe"}</span>
      </div>
      <button className="btn btn-coral full" disabled={loading || !country} data-testid="place-order-button">
        {loading ? <><span className="spinner" /> {text.paymentProcessing}</> : <>{text.placeOrder} · {displayPrice} <ArrowRight size={17} /></>}
      </button>
    </form>
  </main></Shell>;
}

function CheckoutSuccess() {
  const { text } = useLanguage();
  const [params] = useSearchParams();
  const orderId = params.get("order_id");
  const isPending = params.get("pending") === "1";
  const [payStatus, setPayStatus] = useState(isPending ? "pending" : "checking");

  useEffect(() => {
    if (!orderId || payStatus === "paid") return;
    const check = async () => {
      try {
        const { data } = await axios.get(`${API}/payments/status/${orderId}`);
        if (data.payment_status === "paid") setPayStatus("paid");
        else if (data.payment_status === "failed") setPayStatus("failed");
      } catch (_) {}
    };
    check();
    const timer = setInterval(check, 3000);
    return () => clearInterval(timer);
  }, [orderId, payStatus]);

  const isPaid = payStatus === "paid";
  const isFailed = payStatus === "failed";

  return <Shell><div className="center-page" data-testid="checkout-success-page">
    <div className={`success-icon ${isFailed ? "failed" : ""}`}>{isFailed ? "✕" : isPaid ? <Check /> : <span className="spinner" />}</div>
    <div className="eyebrow">{isPaid ? text.confirmed : isFailed ? text.payFailedTitle : text.checkingPayment}</div>
    <h1>{isPaid ? text.paySuccessTitle : isFailed ? text.payFailedDesc : (isPending ? text.payPendingTitle : text.checkingPayment)}</h1>
    <p className="center-sub">{isPaid ? text.paySuccessDesc : isFailed ? text.payFailedDesc : text.payPendingDesc}</p>
    {isPaid && <Link to="/dashboard" className="btn btn-primary" data-testid="track-order-button">{text.track} <ArrowRight size={17} /></Link>}
    {isFailed && <Link to="/checkout" className="btn btn-coral" data-testid="retry-checkout-button">{text.payRetry} <ArrowRight size={17} /></Link>}
    {!isPaid && !isFailed && <Link to="/" className="text-link" data-testid="back-home-link">{text.backHome}</Link>}
  </div></Shell>;
}

function CheckoutCancel() {
  const { text } = useLanguage();
  const [params] = useSearchParams();
  const orderId = params.get("order_id");
  return <Shell><div className="center-page" data-testid="checkout-cancel-page">
    <div className="success-icon" style={{ background: "var(--clr-coral, #f97316)" }}>✕</div>
    <div className="eyebrow">{text.payCancelTitle}</div>
    <h1>{text.payCancelTitle}</h1>
    <p className="center-sub">{text.payCancelDesc}</p>
    <Link to={orderId ? `/checkout` : "/dashboard"} className="btn btn-coral" data-testid="retry-checkout-button">{text.payRetry} <ArrowRight size={17} /></Link>
  </div></Shell>;
}

function Dashboard() {
  const { text } = useLanguage();
  const { user } = useAuth();
  const [stories, setStories] = useState([]);
  const [orders, setOrders] = useState([]);

  useEffect(() => {
    Promise.all([
      axios.get(`${API}/stories`, { withCredentials: true }),
      axios.get(`${API}/orders`, { withCredentials: true }),
    ]).then(([sr, or]) => { setStories(sr.data); setOrders(or.data); }).catch(() => {});
  }, []);

  return <Shell><main className="dashboard">
    <div className="dashboard-head">
      <div>
        <div className="eyebrow"><Heart size={14} /> {text.dashEyebrow}</div>
        <h1>{text.welcomeA} <em>{user?.name?.split(" ")[0] || text.welcomeB}</em></h1>
      </div>
      <Link to="/create" className="btn btn-primary" data-testid="dashboard-create-book-button">{text.createAnother} <Sparkles size={16} /></Link>
    </div>
    <section className="dash-section">
      <div className="section-heading"><h2>{text.stories}</h2><span>{stories.length || 0} {text.saved}</span></div>
      <div className="library-grid">
        {stories.length ? stories.map(story => <Link to={`/storybook/${story.id}`} className="story-card" key={story.id} data-testid={`story-card-${story.id}`}>
          <img src={resolveImage(story.cover_image || (story.pages && story.pages[0] && story.pages[0].image))} alt="Story cover" />
          <div><b>{story.title}</b><small>{text.created} · {languageLabel(themes.find(t => t.name === story.theme) || themes[0])}</small></div>
          <ArrowRight size={16} />
        </Link>) : <div className="empty-state"><BookOpen size={28} /><b>{text.firstWaiting}</b><span>{text.firstDescription}</span><Link to="/create" className="text-link" data-testid="empty-create-book-link">{text.startCreating} <ArrowRight size={14} /></Link></div>}
      </div>
    </section>
    <section className="dash-section">
      <div className="section-heading"><h2>{text.printOrders}</h2><span>{orders.length || 0} {text.ordersCount}</span></div>
      {orders.length ? orders.map(order => <div className="order-row" key={order.id} data-testid={`order-row-${order.id}`}>
        <span className="order-icon"><Package size={18} /></span>
        <div><b>{order.format === "Hardcover" ? text.hardcover : text.softcover} storybook</b><small>{order.status} · {order.city}</small></div>
        <span className="status-pill">{order.status}</span>
      </div>) : <div className="empty-order">{text.noOrders}</div>}
    </section>
  </main></Shell>;
}

function Admin() {
  const { text, language } = useLanguage();
  const [orders, setOrders] = useState([]);
  // Admin calls /api/admin/orders with auth cookie (same-origin)
  useEffect(() => { axios.get(`${API}/admin/orders`, { withCredentials: true }).then(response => setOrders(response.data)).catch(() => {}); }, []);
  const change = async (order, status) => { await axios.patch(`${API}/orders/${order.id}`, { status }, { withCredentials: true }); setOrders(orders.map(item => item.id === order.id ? { ...item, status } : item)); };
  const statusLabels = language === "id" ? { received: "Pesanan diterima", production: "Dalam produksi", shipped: "Dikirim" } : { received: "Order received", production: "In production", shipped: "Shipped" };
  return <Shell><main className="dashboard">
    <div className="dashboard-head">
      <div><div className="eyebrow"><Package size={14} /> {text.adminEyebrow}</div><h1>{text.printA} <em>{text.printB}</em></h1></div>
      <span className="admin-badge">{text.adminView}</span>
    </div>
    <div className="metric-row">
      <div><span>{text.incoming}</span><b>{orders.length}</b></div>
      <div><span>{text.production}</span><b>{orders.filter(o => o.status === "In production").length}</b></div>
      <div><span>{text.shipped}</span><b>{orders.filter(o => o.status === "Shipped").length}</b></div>
    </div>
    <section className="orders-table">
      <div className="table-head"><span>{text.customer}</span><span>{text.book}</span><span>{text.orders}</span></div>
      {orders.length ? orders.map(order => <div className="table-row" key={order.id} data-testid={`admin-order-${order.id}`}>
        <div><b>{order.customer_name}</b><small>{order.email}</small></div>
        <span>{order.format === "Hardcover" ? text.hardcover : text.softcover}</span>
        <select value={order.status} onChange={e => change(order, e.target.value)} data-testid={`order-status-${order.id}`}>
          <option value="Order received">{statusLabels.received}</option>
          <option value="In production">{statusLabels.production}</option>
          <option value="Shipped">{statusLabels.shipped}</option>
        </select>
      </div>) : <div className="empty-order">{text.newOrders}</div>}
    </section>
  </main></Shell>;
}

// ---------- Routing ----------
function AppRouter() {
  const location = useLocation();
  // Detect OAuth callback synchronously to prevent race conditions
  if (location.hash?.includes("session_id=")) return <AuthCallback />;
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/login" element={<Login />} />
      <Route path="/create" element={<ProtectedRoute><Create /></ProtectedRoute>} />
      <Route path="/storybook/:id" element={<Storybook />} />
      <Route path="/checkout" element={<ProtectedRoute><Checkout /></ProtectedRoute>} />
      <Route path="/checkout/success" element={<CheckoutSuccess />} />
      <Route path="/checkout/cancel" element={<CheckoutCancel />} />
      <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
      <Route path="/admin" element={<AdminRoute><Admin /></AdminRoute>} />
    </Routes>
  );
}

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <AuthProvider>
          <AppRouter />
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}

export default App;
