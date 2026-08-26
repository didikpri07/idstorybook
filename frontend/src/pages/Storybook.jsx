import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowRight, BookOpen, Box, ChevronLeft, ChevronRight, Pause, Play, Volume2, VolumeX } from "lucide-react";
import axios from "axios";
import { useLanguage } from "@/i18n";
import { Shell } from "@/components/Shell";
import { API, resolveImage } from "@/lib/constants";

export default function Storybook() {
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
      </main>
    </Shell>
  );
}
