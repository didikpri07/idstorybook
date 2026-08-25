import { useEffect, useRef, useState } from "react";
import "@/App.css";
import "@/Language.css";
import { BrowserRouter, Routes, Route, Link, useParams, useSearchParams } from "react-router-dom";
import axios from "axios";
import { ArrowRight, BookOpen, Box, Check, ChevronLeft, ChevronRight, CircleHelp, CloudUpload, Crown, Heart, Languages, LayoutDashboard, Package, Pause, Play, Sparkles, Volume2, VolumeX, WandSparkles } from "lucide-react";
import { copy, languages, useLanguage } from "@/i18n";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const BACKEND = process.env.REACT_APP_BACKEND_URL;
const resolveImage = src => (src && src.startsWith("/api/") ? `${BACKEND}${src}` : src);
const themes = [{ name: "Moonlit Forest", id: "Hutan Cahaya Bulan", icon: "✦", color: "lavender" }, { name: "Ocean Explorer", id: "Penjelajah Laut", icon: "≈", color: "blue" }, { name: "Dinosaur Valley", id: "Lembah Dinosaurus", icon: "◈", color: "coral" }];
const storyLanguages = [{ code: "en", label: "English", flag: "🇬🇧" }, { code: "id", label: "Bahasa Indonesia", flag: "🇮🇩" }];

function LanguagePanel({ language, setLanguage, text }) {
  const [open, setOpen] = useState(false);
  return <div className="language-wrap"><button className="help-btn language-trigger" onClick={() => setOpen(!open)} aria-label={text.choose} data-testid="language-menu-button"><Languages size={18} /></button>{open && <div className="language-panel" data-testid="language-panel"><b>{text.language}</b><small>{text.interface}</small>{languages.map(item => <button className={language === item.code ? "selected-language" : ""} onClick={() => setLanguage(item.code)} key={item.code} data-testid={`interface-language-${item.code}`}>{item.flag} {item.label}{language === item.code && <Check size={14} />}</button>)}</div>}</div>;
}

function Shell({ children }) { const { language, setLanguage, text } = useLanguage(); return <div className="app-shell"><header className="topbar"><Link to="/" className="brand" data-testid="brand-home"><span className="brand-mark"><BookOpen size={19} /></span><span>Kids <b>Storybook</b></span></Link><nav><Link to="/dashboard" data-testid="nav-dashboard"><LayoutDashboard size={16} /> {text.library}</Link><Link to="/admin" data-testid="nav-admin"><Package size={16} /> {text.orders}</Link></nav><LanguagePanel language={language} setLanguage={setLanguage} text={text} /></header>{children}</div>; }

function SamplePeek() {
  const { text } = useLanguage();
  const [story, setStory] = useState(null);
  const [idx, setIdx] = useState(0);
  const [tick, setTick] = useState(0);
  useEffect(() => { axios.get(`${API}/stories/narrator-demo-01`).then(response => setStory(response.data)).catch(() => setStory(null)); }, []);
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
      <p className="sample-preview" key={idx} data-testid="sample-preview-text">“{page.text}”</p>
      <div className="sample-dots" data-testid="sample-dots">
        {story.pages.map((_, i) => <button key={i} type="button" aria-label={`${text.samplePage} ${i + 1}`} className={i === idx ? "selected" : ""} onClick={() => selectPage(i)} data-testid={`sample-dot-${i}`}><span /></button>)}
      </div>
      <Link to={`/storybook/${story.id}`} className="btn btn-primary sample-cta" data-testid="sample-peek-cta">{text.sampleCta} <ArrowRight size={17} /></Link>
    </div>
  </section>;
}

function Home() { const { text } = useLanguage(); return <Shell><main className="hero"><div className="hero-copy"><div className="eyebrow"><Sparkles size={15} /> {text.homeEyebrow}</div><h1>{text.homeTitleA}<br /><em>{text.homeTitleB}</em></h1><p>{text.homeDescription}</p><div className="hero-actions"><Link to="/create" className="btn btn-primary" data-testid="create-book-button">{text.createBook} <ArrowRight size={17} /></Link><Link to="/dashboard" className="text-link" data-testid="view-library-link">{text.viewLibrary} <BookOpen size={16} /></Link></div><div className="trust"><div className="avatar-stack"><span>🌟</span><span>🦊</span><span>🌈</span><span>+</span></div><span>{text.loved}</span></div></div><div className="hero-art"><div className="sun" /><div className="art-label">{text.heroLabel} <b>{text.heroLabelBold}</b></div><img src="https://images.unsplash.com/photo-1645113614899-000bdab2bbcf?crop=entropy&cs=srgb&fm=jpg&q=85" alt="Whimsical storybook scene" data-testid="hero-image" /><div className="floating-note note-one">✦ <b>{text.madeWonder}</b></div><div className="floating-note note-two">☼ {text.printed}</div></div></main><SamplePeek /><section className="theme-strip"><div><span className="section-kicker">{text.pickChapter}</span><h2>{text.whereGo}</h2></div><div className="theme-cards">{themes.map(theme => <div className={`theme-card ${theme.color}`} key={theme.name} data-testid={`theme-card-${theme.name.toLowerCase().replaceAll(" ", "-")}`}><span>{theme.icon}</span><b>{languageLabel(theme)}</b><small>{text.buildStory}</small></div>)}</div></section></Shell>; }
function languageLabel(theme) { return window.localStorage.getItem("kids-storybook-ui") === "id" ? theme.id : theme.name; }

function Create() {
  const { language, text } = useLanguage();
  const [form, setForm] = useState({ child_name: "", age: 5, gender: "", theme: "Moonlit Forest", photo_base64: "", story_language: "en" });
  const [photoName, setPhotoName] = useState("");
  const [loading, setLoading] = useState(false); const [error, setError] = useState(""); const [preview, setPreview] = useState("");
  const update = event => setForm({ ...form, [event.target.name]: event.target.value });
  const readAsDataUrl = file => new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = reject; reader.readAsDataURL(file); });
  const onPhoto = async event => { const file = event.target.files?.[0]; if (!file) return; setPhotoName(file.name); const dataUrl = await readAsDataUrl(file); setForm(previous => ({ ...previous, photo_base64: dataUrl })); };
  const submit = async event => { event.preventDefault(); setLoading(true); setError(""); try { const response = await axios.post(`${API}/stories`, form, { timeout: 180000 }); setPreview(response.data.id); } catch (err) { const detail = err && err.response && err.response.data && err.response.data.detail; setError(detail || text.createError); } finally { setLoading(false); } };
  if (preview) return <Shell><div className="center-page"><div className="success-icon"><Check /></div><div className="eyebrow">{text.ready}</div><h1>{text.meet} {form.child_name}’s<br /><em>{text.adventure}</em></h1><p className="center-sub">{text.readyDescription} {form.child_name}.</p><Link to={`/storybook/${preview}`} className="btn btn-primary" data-testid="open-storybook-button">{text.openStory} <ArrowRight size={17} /></Link></div></Shell>;
  return <Shell><main className="create-layout"><div className="create-intro"><div className="eyebrow"><WandSparkles size={15} /> {text.createEyebrow}</div><h1>{text.createTitleA}<br /><em>{text.createTitleB}</em></h1><p>{text.createDescription}</p><div className="steps"><span className="active">01</span><i /><span>02</span><i /><span>03</span></div></div><form className="form-panel" onSubmit={submit}>{error && <div className="error-message" role="alert" data-testid="create-error-message">{error}</div>}<label>{text.name}<input name="child_name" value={form.child_name} onChange={update} placeholder={language === "id" ? "contoh: Maya" : "e.g. Maya"} required data-testid="child-name-input" /></label><div className="two-col"><label>{text.age}<select name="age" value={form.age} onChange={update} data-testid="child-age-select">{[3, 4, 5, 6, 7, 8, 9, 10].map(age => <option key={age}>{age}</option>)}</select></label><label>{text.personality}<select name="gender" value={form.gender} onChange={update} required data-testid="child-gender-select"><option value="">{text.choose}</option><option>{language === "id" ? "Pemberani" : "Adventurous"}</option><option>{language === "id" ? "Penasaran" : "Curious"}</option><option>{language === "id" ? "Imajinatif" : "Imaginative"}</option></select></label></div><label>{text.world}<select name="theme" value={form.theme} onChange={update} data-testid="story-theme-select">{themes.map(theme => <option key={theme.name} value={theme.name}>{language === "id" ? theme.id : theme.name}</option>)}</select></label><label className="upload">{text.photo}<div className="upload-box"><CloudUpload size={24} /><span><b>{photoName || text.dropPhoto}</b> {!photoName && text.browse}</span><small>{text.photoHint}</small></div><input type="file" accept="image/*" data-testid="child-photo-input" onChange={onPhoto} /></label><div className="story-language-field"><label>{text.storybook}<select name="story_language" value={form.story_language} onChange={update} data-testid="storybook-language-select">{storyLanguages.map(item => <option value={item.code} key={item.code}>{item.flag} {item.label}</option>)}</select></label><small>{language === "id" ? "Bahasa ini akan digunakan untuk teks buku cerita." : "This language will be used for the story text."}</small></div><button className="btn btn-primary full" disabled={loading} data-testid="generate-story-button">{loading ? <><span className="spinner" /> {text.weaving}</> : <>{text.magic} <WandSparkles size={17} /></>}</button><small className="safe-note">🔒 {text.privacy}</small></form></main></Shell>;
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

  // When the page changes and narration is unlocked, auto-play the new page audio.
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
          {!unlocked && audioSrc ? (
            <button type="button" className="btn btn-primary btn-sm narrator-start" onClick={startReading} data-testid="start-read-aloud-button"><Play size={16} /> {text.readAloud}</button>
          ) : null}
          {unlocked && audioSrc ? (
            <>
              <button type="button" className="icon-btn" onClick={togglePlay} aria-label={playing ? text.stopReading : text.readAloud} data-testid="toggle-play-button">{playing ? <Pause size={18} /> : <Play size={18} />}</button>
              <button type="button" className="icon-btn" onClick={toggleMute} aria-label={muted ? text.unmuteNarrator : text.muteNarrator} data-testid="toggle-mute-button">{muted ? <VolumeX size={18} /> : <Volume2 size={18} />}</button>
              <small className="narrator-hint" data-testid="narrator-hint">{playing ? "◆ " + text.readAloud : text.readAloud}</small>
            </>
          ) : null}
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

function Checkout() { const { text } = useLanguage(); const [params] = useSearchParams(); const [done, setDone] = useState(false); const [error, setError] = useState(""); const [format, setFormat] = useState("Hardcover"); const [form, setForm] = useState({ customer_name: "", email: "", address: "", city: "", postal_code: "", payment_method: "Stripe" }); const update = event => setForm({ ...form, [event.target.name]: event.target.value }); const submit = async event => { event.preventDefault(); setError(""); try { await axios.post(`${API}/orders`, { ...form, story_id: params.get("story_id") || "demo", child_name: params.get("child_name") || "Story friend", format, gift_box: false }); setDone(true); } catch (_) { setError(text.orderError); } }; if (done) return <Shell><div className="center-page"><div className="success-icon"><Check /></div><div className="eyebrow">{text.confirmed}</div><h1>{text.onWayA}<br /><em>{text.onWayB}</em></h1><p className="center-sub">{text.confirmedDescription}</p><Link to="/dashboard" className="btn btn-primary" data-testid="track-order-button">{text.track} <ArrowRight size={17} /></Link></div></Shell>; return <Shell><main className="checkout"><div className="checkout-title"><Link to="/dashboard" className="back-link" data-testid="back-storybook-link"><ChevronLeft size={17} /> {text.checkoutBack}</Link><h1>{text.checkoutTitleA} <em>{text.checkoutTitleB}</em></h1><p>{text.checkoutDescription}</p></div><form className="checkout-form" onSubmit={submit}>{error && <div className="error-message" role="alert" data-testid="checkout-error-message">{error}</div>}<div className="format-row"><h3>{text.cover}</h3><div className="format-options">{[["Hardcover", "$34.00", "★★★★★"], ["Softcover", "$22.00", "★★★★☆"]].map(([name, price, stars]) => <button type="button" onClick={() => setFormat(name)} className={`format-option ${format === name ? "chosen" : ""}`} key={name} data-testid={`format-${name.toLowerCase()}-option`}><span className="cover-icon">▣</span><b>{name === "Hardcover" ? text.hardcover : text.softcover}</b><small>{stars} · {price}</small>{format === name && <Check size={16} />}</button>)}</div></div><div className="field-section"><h3>{text.send}</h3><div className="two-col"><input name="customer_name" placeholder={text.fullName} required onChange={update} data-testid="shipping-name-input" /><input name="email" type="email" placeholder={text.email} required onChange={update} data-testid="shipping-email-input" /></div><input name="address" placeholder={text.address} required onChange={update} data-testid="shipping-address-input" /><div className="two-col"><input name="city" placeholder={text.city} required onChange={update} data-testid="shipping-city-input" /><input name="postal_code" placeholder={text.postal} required onChange={update} data-testid="shipping-postal-input" /></div></div><div className="payment-note"><Crown size={18} /><span><b>{text.secure}</b><small>{text.paymentHint}</small></span><span className="payment-brand">stripe</span></div><button className="btn btn-coral full" data-testid="place-order-button">{text.placeOrder} · {format === "Hardcover" ? "$34.00" : "$22.00"} <ArrowRight size={17} /></button></form></main></Shell>; }

function Dashboard() { const { text } = useLanguage(); const [stories, setStories] = useState([]); const [orders, setOrders] = useState([]); useEffect(() => { Promise.all([axios.get(`${API}/stories`), axios.get(`${API}/orders`)]).then(([storiesResponse, ordersResponse]) => { setStories(storiesResponse.data); setOrders(ordersResponse.data); }); }, []); return <Shell><main className="dashboard"><div className="dashboard-head"><div><div className="eyebrow"><Heart size={14} /> {text.dashEyebrow}</div><h1>{text.welcomeA} <em>{text.welcomeB}</em></h1></div><Link to="/create" className="btn btn-primary" data-testid="dashboard-create-book-button">{text.createAnother} <Sparkles size={16} /></Link></div><section className="dash-section"><div className="section-heading"><h2>{text.stories}</h2><span>{stories.length || 0} {text.saved}</span></div><div className="library-grid">{stories.length ? stories.map(story => <Link to={`/storybook/${story.id}`} className="story-card" key={story.id} data-testid={`story-card-${story.id}`}><img src={resolveImage(story.cover_image || (story.pages && story.pages[0] && story.pages[0].image))} alt="Story cover" /><div><b>{story.title}</b><small>{text.created} · {languageLabel(themes.find(theme => theme.name === story.theme) || themes[0])}</small></div><ArrowRight size={16} /></Link>) : <div className="empty-state"><BookOpen size={28} /><b>{text.firstWaiting}</b><span>{text.firstDescription}</span><Link to="/create" className="text-link" data-testid="empty-create-book-link">{text.startCreating} <ArrowRight size={14} /></Link></div>}</div></section><section className="dash-section"><div className="section-heading"><h2>{text.printOrders}</h2><span>{orders.length || 0} {text.ordersCount}</span></div>{orders.length ? orders.map(order => <div className="order-row" key={order.id} data-testid={`order-row-${order.id}`}><span className="order-icon"><Package size={18} /></span><div><b>{order.format === "Hardcover" ? text.hardcover : text.softcover} storybook</b><small>{order.status} · {order.city}</small></div><span className="status-pill">{order.status}</span></div>) : <div className="empty-order">{text.noOrders}</div>}</section></main></Shell>; }

function Admin() {
  const { text, language } = useLanguage();
  const [orders, setOrders] = useState([]);
  useEffect(() => { axios.get(`${API}/orders`).then(response => setOrders(response.data)); }, []);
  const change = async (order, status) => { await axios.patch(`${API}/orders/${order.id}`, { status }); setOrders(orders.map(item => item.id === order.id ? { ...item, status } : item)); };
  const statusLabels = language === "id" ? { received: "Pesanan diterima", production: "Dalam produksi", shipped: "Dikirim" } : { received: "Order received", production: "In production", shipped: "Shipped" };
  return <Shell><main className="dashboard"><div className="dashboard-head"><div><div className="eyebrow"><Package size={14} /> {text.adminEyebrow}</div><h1>{text.printA} <em>{text.printB}</em></h1></div><span className="admin-badge">{text.adminView}</span></div><div className="metric-row"><div><span>{text.incoming}</span><b>{orders.length}</b></div><div><span>{text.production}</span><b>{orders.filter(order => order.status === "In production").length}</b></div><div><span>{text.shipped}</span><b>{orders.filter(order => order.status === "Shipped").length}</b></div></div><section className="orders-table"><div className="table-head"><span>{text.customer}</span><span>{text.book}</span><span>{text.orders}</span></div>{orders.length ? orders.map(order => <div className="table-row" key={order.id} data-testid={`admin-order-${order.id}`}><div><b>{order.customer_name}</b><small>{order.email}</small></div><span>{order.format === "Hardcover" ? text.hardcover : text.softcover}</span><select value={order.status} onChange={event => change(order, event.target.value)} data-testid={`order-status-${order.id}`}><option value="Order received">{statusLabels.received}</option><option value="In production">{statusLabels.production}</option><option value="Shipped">{statusLabels.shipped}</option></select></div>) : <div className="empty-order">{text.newOrders}</div>}</section></main></Shell>;
}

function App() { return <div className="App"><BrowserRouter><Routes><Route path="/" element={<Home />} /><Route path="/create" element={<Create />} /><Route path="/storybook/:id" element={<Storybook />} /><Route path="/checkout" element={<Checkout />} /><Route path="/dashboard" element={<Dashboard />} /><Route path="/admin" element={<Admin />} /></Routes></BrowserRouter></div>; }
export default App;