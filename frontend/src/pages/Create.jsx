import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, BookOpen, Check, CloudUpload, SmilePlus, Sun, User, WandSparkles } from "lucide-react";
import axios from "axios";
import { useLanguage } from "@/i18n";
import { useAuth } from "@/context/AuthContext";
import { Shell } from "@/components/Shell";
import { CoverPreview } from "@/components/CoverPreview";
import { StylePicker } from "@/components/StylePicker";
import { API, themes, storyLanguages } from "@/lib/constants";

// Key used to stash an in-progress book while an anonymous parent signs in.
export const PENDING_STORY_KEY = "idsb_pending_story";

// Shrink an oversized photo so the whole form fits in localStorage across the OAuth redirect.
const downscalePhoto = (dataUrl, maxDim = 1024) => new Promise(resolve => {
  try {
    const img = new Image();
    img.onload = () => {
      const scale = Math.min(1, maxDim / Math.max(img.width, img.height));
      const w = Math.round(img.width * scale);
      const h = Math.round(img.height * scale);
      const canvas = document.createElement("canvas");
      canvas.width = w; canvas.height = h;
      canvas.getContext("2d").drawImage(img, 0, 0, w, h);
      resolve(canvas.toDataURL("image/jpeg", 0.85));
    };
    img.onerror = () => resolve("");
    img.src = dataUrl;
  } catch { resolve(""); }
});

// Persist the filled form before sending the parent to sign in. Falls back to a
// smaller photo (or none) if the browser storage quota is exceeded.
const persistPendingStory = async data => {
  try {
    localStorage.setItem(PENDING_STORY_KEY, JSON.stringify(data));
    return;
  } catch { /* quota — try a smaller photo */ }
  try {
    const shrunk = data.photo_base64 ? await downscalePhoto(data.photo_base64, 1024) : "";
    localStorage.setItem(PENDING_STORY_KEY, JSON.stringify({ ...data, photo_base64: shrunk }));
  } catch {
    try { localStorage.setItem(PENDING_STORY_KEY, JSON.stringify({ ...data, photo_base64: "" })); } catch { /* give up */ }
  }
};

export default function Create() {
  const { language, text } = useLanguage();
  const { user, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ child_name: "", age: 5, gender: "", theme: "Moonlit Forest", visual_style: "Classic Watercolor", photo_base64: "", story_language: "en", story_prompt: "", page_count: 24 });
  const [photoName, setPhotoName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState("");
  const [processingId, setProcessingId] = useState(null);
  const [elapsed, setElapsed] = useState(0);

  const PROGRESS_STEPS = [
    { label: language === "id" ? `Menulis cerita untuk ${form.child_name || "si kecil"}\u2026` : `Writing a story for ${form.child_name || "your little one"}\u2026`, icon: "\u2726" },
    { label: language === "id" ? "Melukis ilustrasi cerita\u2026" : "Painting story illustrations\u2026", icon: "\u25c9" },
    { label: language === "id" ? "Merekam narasi cerita\u2026" : "Recording the narration\u2026", icon: "\u266a" },
    { label: language === "id" ? "Sentuhan akhir\u2026" : "Adding the final touches\u2026", icon: "\u25c6" },
  ];
  const stepIndex = elapsed < 20 ? 0 : elapsed < 50 ? 1 : elapsed < 70 ? 2 : 3;
  const progress = Math.min(92, (elapsed / 80) * 100);

  const update = event => setForm({ ...form, [event.target.name]: event.target.value });
  const readAsDataUrl = file => new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = reject; reader.readAsDataURL(file); });
  const onPhoto = async event => { const file = event.target.files?.[0]; if (!file) return; setPhotoName(file.name); const dataUrl = await readAsDataUrl(file); setForm(previous => ({ ...previous, photo_base64: dataUrl })); };

  useEffect(() => {
    if (!processingId) return;
    let active = true;
    const elapsedTimer = setInterval(() => setElapsed(e => e + 1), 1000);
    const poll = async () => {
      if (!active) return;
      try {
        const { data } = await axios.get(`${API}/stories/${processingId}`);
        if (data.status === "completed" && active) setPreview(processingId);
        else if (data.status === "failed" && active) { setError(text.createError); setProcessingId(null); setElapsed(0); }
      } catch (err) { console.error("Story status poll failed:", err); }
    };
    const pollTimer = setInterval(poll, 3000);
    poll();
    return () => { active = false; clearInterval(elapsedTimer); clearInterval(pollTimer); };
  }, [processingId, text.createError]);

  const submit = async event => {
    event.preventDefault();
    // Unauthenticated parents fill everything first, then sign in. Stash the form
    // and send them to login; the story generates automatically once they return.
    if (!user) {
      await persistPendingStory({ ...form, photo_name: photoName });
      navigate("/login", { state: { from: { pathname: "/create" } } });
      return;
    }
    startGeneration(form);
  };

  const startGeneration = async payload => {
    setLoading(true); setError("");
    try {
      const response = await axios.post(`${API}/stories`, payload, { timeout: 30000, withCredentials: true });
      setProcessingId(response.data.id);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(detail || text.createError);
    } finally { setLoading(false); }
  };

  // Resume a book the parent started before signing in.
  useEffect(() => {
    if (authLoading || !user) return;
    let raw = null;
    try { raw = localStorage.getItem(PENDING_STORY_KEY); } catch { raw = null; }
    if (!raw) return;
    try { localStorage.removeItem(PENDING_STORY_KEY); } catch { /* ignore */ }
    try {
      const saved = JSON.parse(raw);
      const restored = { ...form, ...saved };
      setForm(restored);
      if (saved.photo_base64) setPhotoName(saved.photo_name || "Your photo");
      startGeneration(restored);
    } catch { /* corrupt payload — ignore */ }
  }, [authLoading, user]);

  if (preview) return (
    <Shell>
      <div className="center-page">
        <div className="success-icon"><Check /></div>
        <div className="eyebrow">{text.ready}</div>
        <h1>{text.meet} {form.child_name}'s<br /><em>{text.adventure}</em></h1>
        <p className="center-sub">{text.readyDescription.replace("{n}", form.page_count)} {form.child_name}.</p>
        <Link to={`/storybook/${preview}`} className="btn btn-primary" data-testid="open-storybook-button">
          {text.openStory} <ArrowRight size={17} />
        </Link>
      </div>
    </Shell>
  );

  if (processingId) {
    const step = PROGRESS_STEPS[stepIndex];
    return (
      <Shell>
        <div className="center-page generating-page" data-testid="generating-page">
          <div className="generating-icon-wrap"><div className="generating-book-pulse"><BookOpen size={32} /></div></div>
          <div className="eyebrow" data-testid="generating-step-label">{step.icon} {step.label}</div>
          <h1>{language === "id" ? "Membuat buku cerita" : "Creating"} <em>{form.child_name}</em>{language === "id" ? "\u2026" : "'s storybook\u2026"}</h1>
          <div className="generating-progress-track">
            <div className="generating-progress-fill" style={{ width: `${progress}%` }} data-testid="generating-progress-bar" />
          </div>
          <p className="center-sub" style={{ marginBottom: 32 }}>{elapsed}s &middot; {language === "id" ? "Biasanya 60\u201390 detik" : "Usually takes 60\u201390 seconds"}</p>
          <div className="generating-steps-list">
            {PROGRESS_STEPS.map((s, i) => (
              <div key={i} className={`generating-step-item ${i < stepIndex ? "step-done" : i === stepIndex ? "step-active" : "step-pending"}`} data-testid={`generating-step-${i}`}>
                <span className="step-icon">{i < stepIndex ? <Check size={13} /> : s.icon}</span>
                <span>{s.label}</span>
              </div>
            ))}
          </div>
          {error && <div className="error-message" role="alert" style={{ marginTop: 24 }} data-testid="create-error-message">{error}</div>}
        </div>
      </Shell>
    );
  }

  return (
    <Shell>
      <main className="create-layout">
        <div className="create-intro">
          <div className="eyebrow"><WandSparkles size={15} /> {text.createEyebrow}</div>
          <h1>{text.createTitleA}<br /><em>{text.createTitleB}</em></h1>
          <p>{text.createDescription}</p>
          <div className="steps"><span className="active">01</span><i /><span>02</span><i /><span>03</span></div>
          <CoverPreview childName={form.child_name} theme={form.theme} photoBase64={form.photo_base64} visualStyle={form.visual_style} />
        </div>
        <form className="form-panel" onSubmit={submit}>
          {error && <div className="error-message" role="alert" data-testid="create-error-message">{error}</div>}
          <label>{text.name}<input name="child_name" value={form.child_name} onChange={update} placeholder={language === "id" ? "contoh: Maya" : "e.g. Maya"} required data-testid="child-name-input" /></label>
          <div className="two-col">
            <label>{text.age}<select name="age" value={form.age} onChange={update} data-testid="child-age-select">{[3, 4, 5, 6, 7, 8, 9, 10].map(age => <option key={age}>{age}</option>)}</select></label>
            <label>{text.personality}<select name="gender" value={form.gender} onChange={update} required data-testid="child-gender-select"><option value="">{text.choose}</option><option>{language === "id" ? "Pemberani" : "Adventurous"}</option><option>{language === "id" ? "Penasaran" : "Curious"}</option><option>{language === "id" ? "Imajinatif" : "Imaginative"}</option></select></label>
          </div>
          <label>{text.world}<select name="theme" value={form.theme} onChange={update} data-testid="story-theme-select">{themes.map(theme => <option key={theme.name} value={theme.name}>{language === "id" ? theme.id : theme.name}</option>)}</select></label>
          <div className="page-count-field">
            <label>{text.pageCountLabel}
              <select
                name="page_count"
                value={form.page_count}
                onChange={e => setForm(f => ({ ...f, page_count: Number(e.target.value) }))}
                data-testid="page-count-select"
              >
                {[8, 16, 24, 32].map(n => <option key={n} value={n}>{n} {text.pagesWord}</option>)}
              </select>
            </label>
            <small>{text.pageCountHelper}</small>
          </div>
          <div className="field-block story-prompt-field">
            <label className="field-label">{text.storyPromptLabel} <span className="optional-tag">{text.storyPromptOptional}</span></label>
            <div className="story-prompt-wrap">
              <textarea
                name="story_prompt"
                value={form.story_prompt}
                onChange={update}
                maxLength={300}
                rows={3}
                placeholder={language === "id"
                  ? "contoh: Anakku sering meninggalkan cangkir di mana-mana. Buat cerita lucu tentang bagaimana ia belajar membereskannya."
                  : "e.g. My 7-year-old doesn't want to sleep over at grandma's. Help them feel brave and excited about the adventure."}
                className="story-prompt-textarea"
                data-testid="story-prompt-textarea"
              />
              <span className={`char-count${form.story_prompt.length > 270 ? " near-limit" : ""}`} data-testid="story-prompt-char-count">{form.story_prompt.length} / 300</span>
            </div>
            <small className="story-prompt-helper">{text.storyPromptHelper}</small>
          </div>
          <div className="field-block">
            <label className="field-label">{text.visualStyle}</label>
            <StylePicker value={form.visual_style} onChange={v => setForm(f => ({ ...f, visual_style: v }))} />
          </div>
          <label className="upload">{text.photo}
            <div className={`upload-box${form.photo_base64 ? " upload-box--filled" : ""}`}>
              {form.photo_base64 ? (
                <>
                  <img src={form.photo_base64} alt="Selected child photo" className="photo-preview-thumb" data-testid="photo-preview-thumb" />
                  <span className="photo-preview-name"><b>{photoName}</b></span>
                  <small>{text.photoChangeHint}</small>
                </>
              ) : (
                <>
                  <CloudUpload size={24} />
                  <span><b>{text.dropPhoto}</b> {text.browse}</span>
                  <small>{text.photoHint}</small>
                </>
              )}
            </div>
            <input type="file" accept="image/*" data-testid="child-photo-input" onChange={onPhoto} />
          </label>
          <div className="photo-tips" aria-label="Photo tips">
            <span className="photo-tip"><Sun size={10} /> {text.photoTipLight}</span>
            <span className="photo-tip"><User size={10} /> {text.photoTipFacing}</span>
            <span className="photo-tip"><SmilePlus size={10} /> {text.photoTipFace}</span>
          </div>
          <div className="story-language-field">
            <label>{text.storybook}<select name="story_language" value={form.story_language} onChange={update} data-testid="storybook-language-select">{storyLanguages.map(item => <option value={item.code} key={item.code}>{item.flag} {item.label}</option>)}</select></label>
            <small>{language === "id" ? "Bahasa ini akan digunakan untuk teks buku cerita." : "This language will be used for the story text."}</small>
          </div>
          <button className="btn btn-primary full" disabled={loading} data-testid="generate-story-button">
            {loading ? <><span className="spinner" /> {text.weaving}</> : <>{text.magic} <WandSparkles size={17} /></>}
          </button>
          <small className="safe-note">🔒 {text.privacy}</small>
        </form>
      </main>
    </Shell>
  );
}
