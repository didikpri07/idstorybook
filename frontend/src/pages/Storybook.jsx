import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowRight, BookOpen, Box, Check, ChevronLeft, ChevronRight, FileDown, Pause, Play, Share2, Volume2, VolumeX } from "lucide-react";
import axios from "axios";
import { useLanguage } from "@/i18n";
import { Shell } from "@/components/Shell";
import { API, BACKEND, resolveImage } from "@/lib/constants";

export default function Storybook() {
  const { text } = useLanguage();
  const { id } = useParams();
  const [story, setStory] = useState(null);
  const [error, setError] = useState("");
  const [page, setPage] = useState(0);
  const [unlocked, setUnlocked] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [muted, setMuted] = useState(false);
  const [copied, setCopied] = useState(false);
  const [generatingPdf, setGeneratingPdf] = useState(false);
  const audioRef = useRef(null);

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
    }
    setGeneratingPdf(false);
  };

  const shareStory = async () => {
    const url = window.location.href;
    if (navigator.share) {
      try { await navigator.share({ title: story?.title, text: `Read "${story?.title}" — a personalized storybook!`, url }); } catch {}
    } else {
      await navigator.clipboard.writeText(url).catch(() => {});
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    }
  };

  useEffect(() => {
    axios.get(`${API}/stories/${id}`)
      .then(response => setStory(response.data))
      .catch(() => setError(text.storyError));
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
  if (story.status === "processing" || !story.pages || !story.pages.length) return (
    <Shell>
      <div className="center-page" data-testid="story-processing-page">
        <div className="generating-icon-wrap"><div className="generating-book-pulse"><BookOpen size={32} /></div></div>
        <div className="eyebrow">{text.storyLoading}</div>
        <h1>Your storybook is<br /><em>being made…</em></h1>
        <p className="center-sub">This usually takes 60–90 seconds. Come back shortly!</p>
        <Link to="/dashboard" className="btn btn-primary" data-testid="back-library-link">{text.backLibrary} <ArrowRight size={17} /></Link>
      </div>
    </Shell>
  );
  if (story.status === "failed") return (
    <Shell>
      <div className="center-page">
        <div className="success-icon" style={{ background: "#fff0e7", color: "#ff776e" }}>!</div>
        <h1>Something went <em>wrong</em></h1>
        <p className="center-sub">Story generation failed. Please try creating a new one.</p>
        <Link to="/create" className="btn btn-primary" data-testid="create-book-button">{text.createBook} <ArrowRight size={17} /></Link>
      </div>
    </Shell>
  );

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
    const el = audioRef.current;
    if (el) { try { await el.play(); setPlaying(true); } catch { setPlaying(false); } }
  };
  const togglePlay = async () => {
    const el = audioRef.current;
    if (!el) return;
    if (el.paused) { try { await el.play(); setPlaying(true); } catch { setPlaying(false); } }
    else { el.pause(); setPlaying(false); }
  };
  const toggleMute = () => { setMuted(m => { const next = !m; if (audioRef.current) audioRef.current.muted = next; return next; }); };
  const onEnded = () => { setPlaying(false); if (!isLast) setPage(p => p + 1); };
  const goPage = next => { setPage(next); };

  return (
    <Shell>
      <main className="reader">
        <div className="reader-head">
          <Link to="/dashboard" className="back-link" data-testid="back-library-link"><ChevronLeft size={17} /> {text.backLibrary}</Link>
          <span className="reader-title"><BookOpen size={16} /> {story.cover?.title || story.title}</span>
          <div className="reader-head-actions">
            <button type="button" className={`btn btn-share ${copied ? "btn-share--copied" : ""}`} onClick={shareStory} data-testid="share-story-button" aria-label={text.shareStory}>
              {copied ? <><Check size={15} /> {text.linkCopied}</> : <><Share2 size={15} /> {text.shareStory}</>}
            </button>
            <button type="button" className={`btn btn-download ${generatingPdf ? "btn-download--busy" : ""}`} onClick={downloadPdf} disabled={generatingPdf} data-testid="download-pdf-button" aria-label={text.downloadPdf}>
              {generatingPdf ? <><span className="spinner spinner-sm" /> {text.generatingPdf}</> : <><FileDown size={15} /> {text.downloadPdf}</>}
            </button>
            <Link to={`/checkout?story_id=${story.id}&child_name=${encodeURIComponent(story.child_name)}`} className="btn btn-coral" data-testid="order-physical-book-button">{text.orderPhysical} <Box size={16} /></Link>
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
              <img src={resolveImage(current.image)} alt="Story illustration" data-testid="storybook-illustration"
                className="story-illustration"
                onError={e => { e.currentTarget.src = `${BACKEND}/api/images/placeholder.png`; }} />
              <span className="page-number">{storyPageIdx + 1} / {story.pages.length}</span>
            </div>
            <div className="book-text">
              <span className="page-kicker">{text.chapter} {storyPageIdx + 1}</span>
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
