import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CloudUpload, SmilePlus, Sun, User, WandSparkles } from "lucide-react";
import axios from "axios";
import { useLanguage } from "@/i18n";
import { useAuth } from "@/context/AuthContext";
import { Shell } from "@/components/Shell";
import { CoverPreview } from "@/components/CoverPreview";
import { StylePicker } from "@/components/StylePicker";
import { VoicePicker } from "@/components/VoicePicker";
import { CreateAccountPrompt } from '@/components/CreateAccountPrompt';
import { clearStoryDraft, DEFAULT_STORY_FORM, prepareStoryPhoto, readStoryDraft, saveStoryDraft } from '@/lib/storyDraft';
import { API, themes, storyLanguages } from "@/lib/constants";

export default function Create() {
  const { language, text } = useLanguage();
  const { user, loading: authLoading, setUser } = useAuth();
  const navigate = useNavigate();
  const [draft] = useState(readStoryDraft);
  const [form, setForm] = useState(() => ({ ...DEFAULT_STORY_FORM, ...draft?.form }));
  const [photoName, setPhotoName] = useState(draft?.photoName || '');
  const [accountPrompt, setAccountPrompt] = useState(false);
  const [photoLoading, setPhotoLoading] = useState(false);
  const submitting = useRef(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const update = event => setForm({ ...form, [event.target.name]: event.target.value });
  const onPhoto = async event => {
    const file = event.target.files?.[0]; if (!file) return;
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 10 * 1024 * 1024) {
      setError(language === 'id' ? 'Pilih JPG, PNG, atau WebP di bawah 10 MB.' : 'Choose a JPG, PNG, or WebP under 10 MB.'); event.target.value = ''; return;
    }
    setPhotoLoading(true);
    try { const dataUrl = await prepareStoryPhoto(file); setPhotoName(file.name); setError(''); setForm(previous => ({ ...previous, photo_base64: dataUrl })); }
    catch { setError(language === 'id' ? 'Foto belum bisa dibaca.' : 'This photo could not be read.'); }
    finally { setPhotoLoading(false); }
  };

  const continueToAccount = destination => {
    try {
      saveStoryDraft(form, photoName);
      navigate(`/${destination}?next=${encodeURIComponent('/create?resume=1')}`);
    } catch {
      setAccountPrompt(false);
      setError(language === 'id' ? 'Browser tidak dapat menyimpan detail cerita untuk sementara. Izinkan penyimpanan browser lalu coba lagi; formulirmu belum dihapus.' : 'Your browser could not keep your story details. Please allow browser storage and try again; your form has not been cleared.');
    }
  };

  const submit = async event => {
    event.preventDefault();
    if (authLoading || photoLoading || loading || submitting.current) return;
    if (!user) { setAccountPrompt(true); return; }
    startGeneration(form);
  };

  const startGeneration = async payload => {
    if (!user || submitting.current) return;
    submitting.current = true;
    setLoading(true); setError("");
    try {
      const response = await axios.post(`${API}/stories`, payload, { timeout: 30000, withCredentials: true });
      clearStoryDraft();
      navigate(`/storybook/${response.data.id}`);
    } catch (err) {
      if (err?.response?.status === 401) { setUser(null); setAccountPrompt(true); return; }
      const detail = err?.response?.data?.detail;
      setError(typeof detail === 'string' ? detail : text.createError);
    } finally { setLoading(false); submitting.current = false; }
  };

  return (
    <Shell>
      <CreateAccountPrompt open={accountPrompt} onOpenChange={setAccountPrompt} onContinue={continueToAccount} />
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
            <label>{text.personality}<select name="gender" value={form.gender} onChange={update} required data-testid="child-gender-select"><option value="">{text.choose}</option><option value="Adventurous">{language === "id" ? "Pemberani" : "Adventurous"}</option><option value="Curious">{language === "id" ? "Penasaran" : "Curious"}</option><option value="Imaginative">{language === "id" ? "Imajinatif" : "Imaginative"}</option></select></label>
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
          <VoicePicker value={form.voice_id} onChange={voice_id => setForm(f => ({ ...f, voice_id }))} />
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
            <input type="file" accept="image/jpeg,image/png,image/webp" disabled={photoLoading || loading} data-testid="child-photo-input" onChange={onPhoto} />
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
          <button className="btn btn-primary full" disabled={loading || authLoading || photoLoading} data-testid="generate-story-button">
            {loading ? <><span className="spinner" /> {text.weaving}</> : <>{!user ? (language === 'id' ? 'Lanjutkan untuk membuat cerita' : 'Continue to create my story') : text.magic} <WandSparkles size={17} /></>}
          </button>
          {!user && <small className="guest-limit-note" data-testid="guest-story-limit-note">{language === 'id' ? 'Isi detailnya sekarang. ' : 'Fill in the details now. '}<button type="button" className="inline-signup-button" onClick={() => continueToAccount('signup')} data-testid="create-signup-link">{language === 'id' ? 'Buat akun untuk membuat dan menyimpan ceritamu.' : 'Sign up to create and save your story.'}</button></small>}
          <small className="safe-note">🔒 {text.privacy}</small>
        </form>
      </main>
    </Shell>
  );
}
