import { VISUAL_STYLES } from "@/lib/constants";

export function StylePicker({ value, onChange }) {
  return (
    <div className="style-picker" data-testid="style-picker">
      {VISUAL_STYLES.map(s => (
        <button
          type="button"
          key={s.id}
          className={`style-card ${value === s.id ? "chosen" : ""}`}
          onClick={() => onChange(s.id)}
          data-testid={`style-card-${s.id.toLowerCase().replace(/\s+/g, "-")}`}
        >
          <div className="style-swatch" style={{ background: s.preview }}>{s.icon}</div>
          <b>{s.id}</b>
          <small>{s.desc}</small>
        </button>
      ))}
    </div>
  );
}
