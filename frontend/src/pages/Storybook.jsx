import { useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { ArrowRight, BookOpen, Box, Check, ChevronLeft, ChevronRight, FileDown, Pause, Play, Share2, Volume2, VolumeX } from "lucide-react";
import axios from "axios";
import { useLanguage } from "@/i18n";
import { Shell } from "@/components/Shell";
import { API, BACKEND, resolveImage } from "@/lib/constants";
import { useAuth } from '@/context/AuthContext';
import { GenerationProgress } from '@/components/GenerationProgress';
import { GuestSavePrompt } from '@/components/GuestSavePrompt';
import { SentenceText } from '@/components/SentenceText';
import { Button } from '@/components/ui/button';

export default function Storybook() {
  const { text, language } = useLanguage();
  const { user } = useAuth();
  const { id } = useParams();
  const [params] = useSearchParams();
  const shareToken = params.get('share');
  const [story, setStory] = useState(null);
  const [error, setError] = useState("");
  const [page, setPage] = useState(0);
  const [unlocked, setUnlocked] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(false);
  const [copied, setCopied] = useState(false);
  const [generatingPdf, setGeneratingPdf] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [notice, setNotice] = useState('');
  const [currentMs, setCurrentMs] = useState(0);
  const audioRef = useRef(null);
  const pendingSeek = useRef(null);

  // ---------- helpers ----------
  const toDataUrl = async src => {
    if (!src) return null;
    const url = resolveImage(src);
    if (url.startsWith("data:")) return url;
    try {
      const r = await fetch(url);
      if (!r.ok) return null;
      const blob = await r.blob();
      return new Promise(res => { const fr = new FileReader(); fr.onloadend = () => res(fr.result); fr.readAsDataURL(blob); });
    } catch { return null; }
  };

  const imgFormat = dataUrl => {
    if (!dataUrl) return "PNG";
    if (dataUrl.startsWith("data:image/jpeg") || dataUrl.startsWith("data:image/jpg")) return "JPEG";
    return "PNG";
  };

  const downloadPdf = async () => {
    setGeneratingPdf(true);
    try {
      const { jsPDF } = await import("jspdf");
      // 1:1 square — 160×160mm
      const SZ = 160;
      const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: [SZ, SZ] });
      const W = SZ, H = SZ;
      const coverData = story.cover || { title: story.title, image: story.cover_image };

      // Helper — fill a rectangle with a landscape (1.6:1) image, center-cropped
      const fillRect = (dataUrl, x, y, w, h) => {
        if (!dataUrl) return;
        const fmt = imgFormat(dataUrl);
        const naturalImgW = h * 1.6; // scale by height → wider than w
        const naturalImgH = h;
        if (naturalImgW > w) {
          // landscape wider than target → crop sides (center)
          doc.addImage(dataUrl, fmt, x - (naturalImgW - w) / 2, y, naturalImgW, naturalImgH, undefined, "MEDIUM");
        } else {
          // portrait or square → scale by width
          const scaledH = w / 1.6;
          doc.addImage(dataUrl, fmt, x, y - (scaledH - h) / 2, w, scaledH, undefined, "MEDIUM");
        }
      };

      // ─────────────────── COVER PAGE ───────────────────
      // 1. Dark deep-space background
      doc.setFillColor(8, 5, 25);
      doc.rect(0, 0, W, H, "F");

      // 2. Full-bleed illustration — center-cropped to square
      const coverImg = await toDataUrl(coverData.image || story.pages[0]?.image);
      if (coverImg) fillRect(coverImg, 0, 0, W, H);

      // 3. Gradient overlay — transparent → deep navy, bottom 62% of page
      for (let i = 0; i < 32; i++) {
        const opacity = Math.pow(i / 31, 1.4);
        doc.setGState(new doc.GState({ opacity }));
        doc.setFillColor(8, 5, 25);
        const bandY = H * 0.38 + (i / 32) * H * 0.62;
        doc.rect(0, bandY, W, (H * 0.62 / 32) + 0.5, "F");
      }
      doc.setGState(new doc.GState({ opacity: 1 }));

      // 4. Solid bottom strip for branding
      doc.setFillColor(8, 5, 25);
      doc.rect(0, H - 14, W, 14, "F");

      // 5. "A STORY FOR" eyebrow
      doc.setFont("helvetica", "bold");
      doc.setFontSize(6.5);
      doc.setTextColor(155, 132, 205);
      const eyebrow = story.story_language === "id" ? "SEBUAH CERITA UNTUK" : "A STORY FOR";
      doc.text(eyebrow, W / 2, H * 0.60, { align: "center", charSpace: 2.2 });

      // 6. Big cover title — 2/3 down the page, large and impactful
      doc.setFont("helvetica", "bold");
      doc.setFontSize(29);
      doc.setTextColor(250, 243, 255);
      const titleLines = doc.splitTextToSize(coverData.title, W - 12);
      const titleY = H * 0.68;
      doc.text(titleLines, W / 2, titleY, { align: "center", lineHeightFactor: 1.2 });

      // 7. Child name beneath title
      const nameY = titleY + titleLines.length * 9.8 + 5;
      doc.setFont("helvetica", "normal");
      doc.setFontSize(11.5);
      doc.setTextColor(188, 168, 232);
      doc.text(story.child_name, W / 2, nameY, { align: "center" });

      // 8. Brand footer
      doc.setFont("helvetica", "bold");
      doc.setFontSize(6);
      doc.setTextColor(95, 80, 140);
      doc.text("IDStorybook", W / 2, H - 4.5, { align: "center", charSpace: 2 });

      // ─────────────────── STORY PAGES ───────────────────
      // Image is 1024×640 (1.6:1). At full page width (160mm) → natural height = 100mm.
      const ILLUS_H = W / 1.6; // 100mm — no distortion, no crop

      for (let i = 0; i < story.pages.length; i++) {
        doc.addPage();
        const p = story.pages[i];

        // Warm off-white background
        doc.setFillColor(254, 252, 249);
        doc.rect(0, 0, W, H, "F");

        // Illustration — full width, natural aspect
        const img = await toDataUrl(p.image);
        if (img) {
          doc.addImage(img, imgFormat(img), 0, 0, W, ILLUS_H, undefined, "MEDIUM");
        } else {
          doc.setFillColor(232, 226, 250);
          doc.rect(0, 0, W, ILLUS_H, "F");
          doc.setFontSize(26);
          doc.setTextColor(160, 140, 210);
          doc.text("✦", W / 2, ILLUS_H / 2 + 5, { align: "center" });
        }

        // Thin shadow strip below illustration
        doc.setGState(new doc.GState({ opacity: 0.07 }));
        doc.setFillColor(0, 0, 0);
        doc.rect(0, ILLUS_H, W, 3.5, "F");
        doc.setGState(new doc.GState({ opacity: 1 }));

        // White text card
        const cardY = ILLUS_H + 2.5;
        const cardH = H - cardY - 12;
        doc.setFillColor(255, 255, 255);
        doc.roundedRect(7, cardY, W - 14, cardH, 3.5, 3.5, "F");

        // Story text — vertically centered in card
        doc.setFont("helvetica", "normal");
        doc.setFontSize(12.5);
        doc.setTextColor(28, 18, 52);
        const textLines = doc.splitTextToSize(p.text, W - 26);
        const lineH = 12.5 * 1.55 * 0.352778; // mm per line
        const textBlockH = textLines.length * lineH;
        const textStartY = cardY + (cardH - textBlockH) / 2 + lineH * 0.85;
        doc.text(textLines, W / 2, textStartY, { align: "center", lineHeightFactor: 1.55 });

        // Page number
        doc.setFont("helvetica", "normal");
        doc.setFontSize(7);
        doc.setTextColor(165, 152, 195);
        doc.text(`${i + 1}  ·  IDStorybook`, W / 2, H - 4, { align: "center" });
      }

      const filename = `${story.child_name.replace(/\s+/g, "-")}-IDStorybook.pdf`;
      doc.save(filename);
    } catch (err) {
      console.error("PDF generation failed:", err);
      setNotice(language === 'id' ? 'PDF belum dapat diunduh. Coba lagi.' : 'The PDF could not be downloaded. Please try again.');
    }
    setGeneratingPdf(false);
  };

  const shareStory = async () => {
    try {
      const url = story.read_only ? window.location.href : (await axios.post(`${API}/stories/${id}/share`)).data.url;
      if (navigator.share) await navigator.share({ title: story.title, url });
      else { await navigator.clipboard.writeText(url); setCopied(true); setTimeout(() => setCopied(false), 2500); }
    } catch (e) { if (e.name !== 'AbortError') setNotice(language === 'id' ? 'Tautan belum bisa dibagikan.' : 'The link could not be shared. Please try again.'); }
  };

  const loadStory = async () => {
    const { data } = await axios.get(`${API}/stories/${id}`, { params: shareToken ? { share: shareToken } : {} });
    setStory(data);
  };

  const retry = async () => {
    setRetrying(true); setNotice('');
    try { await axios.post(`${API}/stories/${id}/retry`); await loadStory(); }
    catch { setNotice(language === 'id' ? 'Belum dapat melanjutkan. Coba lagi sebentar.' : 'Could not resume just now. Please try again.'); }
    finally { setRetrying(false); }
  };

  useEffect(() => {
    let active = true;
    setError(''); setStory(null); setPage(0); setUnlocked(false);
    axios.get(`${API}/stories/${id}`, { params: shareToken ? { share: shareToken } : {} })
      .then(response => { if (active) setStory(response.data); })
      .catch(() => { if (active) setError(text.storyError); });
    return () => { active = false; };
  }, [id, shareToken, text.storyError, user]);

  useEffect(() => { setCurrentMs(0); setPlaying(false); }, [page]);

  useEffect(() => {
    if (!unlocked || !story) return;
    const el = audioRef.current;
    if (!el) return;
    const start = () => {
      // Seeking before metadata arrives can be silently discarded by the browser.
      if (el !== audioRef.current) return;
      el.currentTime = (pendingSeek.current ?? 0) / 1000;
      pendingSeek.current = null;
      el.play().then(() => setPlaying(true)).catch(() => setPlaying(false));
    };
    if (el.readyState >= 1) start();
    else el.addEventListener('loadedmetadata', start, { once: true });
    return () => el.removeEventListener('loadedmetadata', start);
  }, [page, unlocked, story]);

  if (error) return <Shell><div className="center-page"><div className="error-message" role="alert" data-testid="storybook-error-message">{error}</div><Link to={`/login?next=${encodeURIComponent(`/storybook/${id}`)}`} className="btn btn-primary" data-testid="story-login-link">{text.signIn}</Link></div></Shell>;
  if (!story) return <Shell><div className="center-page"><span className="spinner" /><p>{text.storyLoading}</p></div></Shell>;
  if (['processing', 'generating'].includes(story.status)) return <Shell><GenerationProgress storyId={id} childName={story.child_name} onReady={loadStory} /></Shell>;
  const partial = ['partial', 'failed'].includes(story.status);
  const partialBanner = partial && <section className="partial-banner" data-testid="partial-story-banner"><div><strong data-testid="partial-story-title">{language === 'id' ? 'Keajaibannya dijeda, bukan hilang.' : 'A little pause. No magic lost.'}</strong><p data-testid="partial-story-description">{language === 'id' ? `${story.pages.filter(p => p.complete || (p.image && p.audio)).length} dari ${story.page_count} halaman selesai. Kemajuanmu tersimpan.` : `${story.pages.filter(p => p.complete || (p.image && p.audio)).length} of ${story.page_count} pages complete. Your progress is saved.`}</p></div>{!story.read_only && <Button className="btn btn-primary" onClick={retry} disabled={retrying} data-testid="retry-remaining-pages-button">{retrying ? <span className="spinner" /> : (language === 'id' ? 'Coba lagi halaman tersisa' : 'Retry remaining pages')}</Button>}</section>;
  if (!story.pages?.length) return <Shell><main className="reader" data-testid="story-empty-recovery">{partialBanner}{notice && <div className="error-message" role="alert" data-testid="reader-notice">{notice}</div>}{story.is_guest && !story.read_only && <GuestSavePrompt storyId={id} />}<Link to="/dashboard" className="back-link" data-testid="empty-story-library-link">{text.backLibrary}<ArrowRight size={15} /></Link></main></Shell>;

  // --- Cover + page indexing ---
  const hasCover = Boolean(story.cover?.image);
  const totalPages = hasCover ? 1 + story.pages.length : story.pages.length;
  const isCoverPage = hasCover && page === 0;
  const storyPageIdx = hasCover ? page - 1 : page;
  const current = isCoverPage ? null : story.pages[storyPageIdx];
  const isLast = page === totalPages - 1;
  const audioSrc = (!isCoverPage && current?.audio) ? resolveImage(current.audio) : null;

  const startReading = async () => {
    setUnlocked(true);
  };
  const seekSentence = async startMs => {
    const el = audioRef.current;
    if (!el) return;
    pendingSeek.current = startMs;
    setCurrentMs(startMs);
    if (!unlocked) { setUnlocked(true); return; }
    if (el.readyState >= 1) {
      el.currentTime = startMs / 1000; pendingSeek.current = null;
      try { await el.play(); setPlaying(true); } catch { setPlaying(false); }
    }
  };
  const togglePlay = async () => {
    const el = audioRef.current;
    if (!el) return;
    if (el.paused) { try { await el.play(); setPlaying(true); } catch { setPlaying(false); } }
    else { el.pause(); setPlaying(false); }
  };
  const toggleMute = () => { setMuted(m => { const next = !m; if (audioRef.current) audioRef.current.muted = next; return next; }); };
  const onEnded = () => { setPlaying(false); setCurrentMs(0); if (!isLast) setPage(p => p + 1); };
  const goPage = next => {
    // Manual turns pause narration; automatic end-of-audio turns keep reading.
    audioRef.current?.pause(); setPlaying(false); setCurrentMs(0); setUnlocked(false);
    pendingSeek.current = null; setPage(next);
  };

  return (
    <Shell>
      <main className="reader">
        {partialBanner}
        {notice && <div className="error-message" role="alert" data-testid="reader-notice">{notice}</div>}
        {story.is_guest && !story.read_only && <GuestSavePrompt storyId={id} />}
        <div className="reader-head">
          <Link to="/dashboard" className="back-link" data-testid="back-library-link"><ChevronLeft size={17} /> {text.backLibrary}</Link>
          <span className="reader-title" data-testid="reader-story-title"><BookOpen size={16} /> {story.cover?.title || story.title}</span>
          <div className="reader-head-actions">
            {(user || story.read_only) && <button type="button" className={`btn btn-share ${copied ? "btn-share--copied" : ""}`} onClick={shareStory} data-testid="share-story-button" aria-label={text.shareStory}>
              {copied ? <><Check size={15} /> {text.linkCopied}</> : <><Share2 size={15} /> {text.shareStory}</>}
            </button>}
            <button type="button" className={`btn btn-download ${generatingPdf ? "btn-download--busy" : ""}`} onClick={downloadPdf} disabled={generatingPdf} data-testid="download-pdf-button" aria-label={text.downloadPdf}>
              {generatingPdf ? <><span className="spinner spinner-sm" /> {text.generatingPdf}</> : <><FileDown size={15} /> {text.downloadPdf}</>}
            </button>
            {!partial && !story.read_only && <Link to={`/checkout?story_id=${story.id}&child_name=${encodeURIComponent(story.child_name)}`} className="btn btn-coral" data-testid="order-physical-book-button">{text.orderPhysical} <Box size={16} /></Link>}
          </div>
        </div>

        {isCoverPage ? (
          <div className="book book--cover-view" data-testid="storybook-cover-page">
            <div className="cover-page-full">
              <img src={resolveImage(story.cover.image)} alt="Story cover" className="cover-page-img" data-testid="cover-illustration"
                onError={e => { e.currentTarget.style.opacity = "0.15"; }} />
              <div className="cover-page-overlay">
                <span className="cover-page-tag">{text.storyFor}</span>
                <h2 className="cover-page-title" data-testid="cover-title">{story.cover.title}</h2>
                <p className="cover-page-name">{story.child_name}</p>
                <small className="cover-page-brand">IDStorybook</small>
              </div>
            </div>
            <div className="reader-controls reader-controls--cover">
              <button aria-label={text.previous} onClick={() => goPage(Math.max(0, page - 1))} disabled={page === 0} data-testid="previous-page-button"><ChevronLeft /></button>
              <div className="dots">
                {Array.from({ length: totalPages }).map((_, i) => <span className={i === page ? "selected" : ""} key={i} />)}
              </div>
              <button aria-label={text.next} onClick={() => goPage(Math.min(totalPages - 1, page + 1))} disabled={isLast} data-testid="next-page-button"><ChevronRight /></button>
            </div>
          </div>
        ) : (
          <div className="book">
            <div className="book-image">
              <img src={resolveImage(current.image) || `${BACKEND}/api/images/placeholder.png`} alt="Story illustration" data-testid="storybook-illustration"
                className="story-illustration"
                onError={e => { e.currentTarget.src = `${BACKEND}/api/images/placeholder.png`; }} />
              <span className="page-number" data-testid="storybook-page-number">{storyPageIdx + 1} / {story.pages.length}</span>
            </div>
            <div className="book-text">
              <span className="page-kicker">{text.chapter} {storyPageIdx + 1}</span>
              <SentenceText page={current} currentMs={currentMs} playing={playing} onSeek={seekSentence} />
              {audioSrc ? <audio key={`${id}-${page}`} ref={audioRef} src={audioSrc} preload="auto" muted={muted} onTimeUpdate={e => { if (e.currentTarget === audioRef.current) setCurrentMs(e.currentTarget.currentTime * 1000); }} onEnded={onEnded} onPlay={e => { setCurrentMs(e.currentTarget.currentTime * 1000); setPlaying(true); }} onPause={() => setPlaying(false)} onError={() => setNotice(language === 'id' ? 'Audio belum bisa diputar.' : 'This audio could not be played.')} data-testid="narrator-audio" /> : null}
              <div className="narrator-controls" data-testid="narrator-controls">
                {!unlocked && audioSrc ? <button type="button" className="btn btn-primary btn-sm narrator-start" onClick={startReading} data-testid="start-read-aloud-button"><Play size={16} /> {text.readAloud}</button> : null}
                {unlocked && audioSrc ? <>
                  <button type="button" className="icon-btn" onClick={togglePlay} aria-label={playing ? text.stopReading : text.readAloud} data-testid="toggle-play-button">{playing ? <Pause size={18} /> : <Play size={18} />}</button>
                  <button type="button" className="icon-btn" onClick={toggleMute} aria-label={muted ? text.unmuteNarrator : text.muteNarrator} data-testid="toggle-mute-button">{muted ? <VolumeX size={18} /> : <Volume2 size={18} />}</button>
                  <small className="narrator-hint" data-testid="narrator-hint">{playing ? "◆ " + text.readAloud : text.readAloud}</small>
                </> : null}
                {!audioSrc ? <small className="narrator-hint" data-testid="narrator-missing">{text.narrationUnavailable}</small> : null}
                {audioSrc && <small className="narrator-voice-name" data-testid="reader-narrator-voice">{story.narrator_voice}</small>}
              </div>
              <div className="reader-controls">
                <button aria-label={text.previous} onClick={() => goPage(Math.max(0, page - 1))} disabled={page === 0} data-testid="previous-page-button"><ChevronLeft /></button>
                <div className="dots">{Array.from({ length: totalPages }).map((_, i) => <span className={i === page ? "selected" : ""} key={i} />)}</div>
                <button aria-label={text.next} onClick={() => goPage(Math.min(totalPages - 1, page + 1))} disabled={isLast} data-testid="next-page-button"><ChevronRight /></button>
              </div>
            </div>
          </div>
        )}
      </main>
    </Shell>
  );
}
