import { User } from "lucide-react";
import { COVER_THEMES } from "@/lib/constants";

export function CoverPreview({ childName, theme, photoBase64, visualStyle }) {
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
          <div className="cover-tagline">{visualStyle || "Classic Watercolor"}</div>
          <div className="cover-brand-label">Kids Storybook</div>
        </div>
      </div>
      <p className="cover-caption">Live cover preview · updates as you type</p>
    </div>
  );
}
