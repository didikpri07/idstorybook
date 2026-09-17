import { Link } from "react-router-dom";
import { ArrowRight, BookOpen, Sparkles } from "lucide-react";
import { useLanguage } from "@/i18n";
import { Shell } from "@/components/Shell";
import { SamplePeek } from "@/components/SamplePeek";
import { themes } from "@/lib/constants";

function languageLabel(theme) {
  return window.localStorage.getItem("kids-storybook-ui") === "id" ? theme.id : theme.name;
}

export default function Home() {
  const { text } = useLanguage();
  return (
    <Shell>
      <main className="hero">
        <div className="hero-copy">
          <div className="eyebrow"><Sparkles size={15} /> {text.homeEyebrow}</div>
          <h1>{text.homeTitleA}<br /><em>{text.homeTitleB}</em></h1>
          <p>{text.homeDescription}</p>
          <div className="hero-actions">
            <Link to="/create" className="btn btn-primary" data-testid="create-book-button">{text.createBook} <ArrowRight size={17} /></Link>
            <Link to="/dashboard" className="text-link" data-testid="view-library-link">{text.viewLibrary} <BookOpen size={16} /></Link>
          </div>
          <div className="trust">
            <div className="avatar-stack"><span>🌟</span><span>🦊</span><span>🌈</span><span>+</span></div>
            <span>{text.loved}</span>
          </div>
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
        <div>
          <span className="section-kicker">Pick Their Story World</span>
          <h2>{text.whereGo}</h2>
        </div>
        <div className="theme-cards">
          {themes.map(theme => (
            <div className={`theme-card ${theme.color}`} key={theme.name} data-testid={`theme-card-${theme.name.toLowerCase().replaceAll(" ", "-")}`}>
              <span>{theme.icon}</span>
              <b>{languageLabel(theme)}</b>
              <small>{text.buildStory}</small>
            </div>
          ))}
        </div>
      </section>
    </Shell>
  );
}
