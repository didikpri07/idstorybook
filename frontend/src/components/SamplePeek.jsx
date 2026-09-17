import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Sparkles, Volume2 } from "lucide-react";
import axios from "axios";
import { useLanguage } from "@/i18n";
import { API, resolveImage } from "@/lib/constants";

export function SamplePeek() {
  const { text } = useLanguage();
  const [story, setStory] = useState(null);
  const [idx, setIdx] = useState(0);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    axios.get(`${API}/stories/${encodeURIComponent("narrator-demo-01")}`)
      .then(response => setStory(response.data))
      .catch(() => setStory(null));
  }, []);

  useEffect(() => {
    if (!story || !story.pages || story.pages.length < 2) return;
    const timer = setInterval(() => setIdx(previous => (previous + 1) % story.pages.length), 4200);
    return () => clearInterval(timer);
  }, [story, tick]);

  if (!story || !story.pages || !story.pages.length) return null;
  const page = story.pages[idx];
  const selectPage = i => { setIdx(i); setTick(previous => previous + 1); };

  return (
    <section className="sample" data-testid="sample-peek-section">
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
          {story.pages.map((_, i) => (
            <button key={i} type="button" aria-label={`${text.samplePage} ${i + 1}`} className={i === idx ? "selected" : ""} onClick={() => selectPage(i)} data-testid={`sample-dot-${i}`}>
              <span />
            </button>
          ))}
        </div>
        <Link to={`/storybook/${story.id}`} className="btn btn-primary sample-cta" data-testid="sample-peek-cta">
          {text.sampleCta} <ArrowRight size={17} />
        </Link>
      </div>
    </section>
  );
}
