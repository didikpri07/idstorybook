import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowRight, BookOpen, Box, Check, ChevronLeft, ChevronRight, FileDown, Pause, Play, Share2, Volume2, VolumeX } from "lucide-react";
import axios from "axios";
import { useLanguage } from "@/i18n";
import { Shell } from "@/components/Shell";
import { API, BACKEND, COVER_THEMES, resolveImage } from "@/lib/constants";

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
      const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a5" });
      const W = doc.internal.pageSize.getWidth();
      const H = doc.internal.pageSize.getHeight();
      const theme = COVER_THEMES[story.theme] || COVER_THEMES["Moonlit Forest"];

      // --- Cover page ---
      doc.setFillColor(15, 12, 41);
      doc.rect(0, 0, W, H, "F");
      const coverSrc = story.cover_image || story.pages[0]?.image;
      const coverImg = await toDataUrl(coverSrc);
      if (coverImg) {
        doc.addImage(coverImg, imgFormat(coverImg), 0, 0, W, H * 0.62, undefined, "MEDIUM");
        // dark gradient overlay over bottom of cover image
        doc.setFillColor(15, 12, 41);
        doc.rect(0, H * 0.52, W, H * 0.12, "F");
      }
      // Title
      doc.setFont("helvetica", "bold");
      doc.setFontSize(20);
      doc.setTextColor(230, 220, 255);
      const titleLines = doc.splitTextToSize(story.title, W - 20);
      doc.text(titleLines, W / 2, H * 0.67, { align: "center", lineHeightFactor: 1.3 });
      // Child name
      doc.setFont("helvetica", "normal");
      doc.setFontSize(12);
      doc.setTextColor(180, 165, 220);
      doc.text(`A story for ${story.child_name}`, W / 2, H * 0.67 + titleLines.length * 8 + 5, { align: "center" });
      // Brand footer
      doc.setFontSize(8);
      doc.setTextColor(100, 90, 140);
      doc.text("IDStorybook · idstorybook.com", W / 2, H - 7, { align: "center" });

      // --- Story pages ---
      for (let i = 0; i < story.pages.length; i++) {
        doc.addPage();
        const p = story.pages[i];
        const IMG_H = H * 0.56;

        // White page bg
        doc.setFillColor(252, 250, 255);
        doc.rect(0, 0, W, H, "F");

        // Illustration
        const img = await toDataUrl(p.image);
        if (img) {
          doc.addImage(img, imgFormat(img), 0, 0, W, IMG_H, undefined, "MEDIUM");
        } else {
          doc.setFillColor(225, 218, 245);
          doc.rect(0, 0, W, IMG_H, "F");
          doc.setFontSize(28);
          doc.text("✦", W / 2, IMG_H / 2 + 5, { align: "center" });
        }

        // Text card
        const cardY = IMG_H + 5;
        const cardH = H - cardY - 14;
        doc.setFillColor(255, 255, 255);
        doc.roundedRect(8, cardY, W - 16, cardH, 3, 3, "F");

        // Story text
        doc.setFont("helvetica", "normal");
        doc.setFontSize(10.5);
        doc.setTextColor(35, 25, 60);
        const lines = doc.splitTextToSize(p.text, W - 28);
        doc.text(lines, W / 2, cardY + 9, { align: "center", lineHeightFactor: 1.45 });

        // Page number + brand
        doc.setFontSize(7.5);
        doc.setTextColor(160, 148, 190);
        doc.text(`${i + 1} / ${story.pages.length}  ·  IDStorybook`, W / 2, H - 4, { align: "center" });
      }

      // --- Download ---
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

  return (
    <Shell>
      <main className="reader">
        <div className="reader-head">
          <Link to="/dashboard" className="back-link" data-testid="back-library-link"><ChevronLeft size={17} /> {text.backLibrary}</Link>
          <span className="reader-title"><BookOpen size={16} /> {story.title}</span>
          <div className="reader-head-actions">
            <button
              type="button"
              className={`btn btn-share ${copied ? "btn-share--copied" : ""}`}
              onClick={shareStory}
              data-testid="share-story-button"
              aria-label={text.shareStory}
            >
              {copied ? <><Check size={15} /> {text.linkCopied}</> : <><Share2 size={15} /> {text.shareStory}</>}
            </button>
            <button
              type="button"
              className={`btn btn-download ${generatingPdf ? "btn-download--busy" : ""}`}
              onClick={downloadPdf}
              disabled={generatingPdf}
              data-testid="download-pdf-button"
              aria-label={text.downloadPdf}
            >
              {generatingPdf
                ? <><span className="spinner spinner-sm" /> {text.generatingPdf}</>
                : <><FileDown size={15} /> {text.downloadPdf}</>}
            </button>
            <Link to={`/checkout?story_id=${story.id}&child_name=${encodeURIComponent(story.child_name)}`} className="btn btn-coral" data-testid="order-physical-book-button">{text.orderPhysical} <Box size={16} /></Link>
          </div>
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
      </main>
    </Shell>
  );
}
