export const COUNTRIES = ["Australia", "Canada", "Germany", "Indonesia", "Malaysia", "Netherlands", "New Zealand", "Philippines", "Singapore", "United Kingdom", "United States", "Other"];

export const VISUAL_STYLES = [
  { id: "Classic Watercolor", icon: "◌", preview: "linear-gradient(135deg,#f3e8ff 0%,#e8f4f8 50%,#fff8e8 100%)", desc: "Soft & dreamy" },
  { id: "3D Animation",       icon: "◉", preview: "linear-gradient(135deg,#dbeafe 0%,#bfdbfe 50%,#e0f2fe 100%)", desc: "Bright & playful" },
  { id: "Comic Book",         icon: "▣", preview: "linear-gradient(135deg,#fef3c7 0%,#fde68a 50%,#fecaca 100%)", desc: "Bold & expressive" },
  { id: "Claymation",         icon: "◆", preview: "linear-gradient(135deg,#d1fae5 0%,#a7f3d0 50%,#ecfdf5 100%)", desc: "Tactile & fun" },
  { id: "Pencil Sketch",      icon: "⊘", preview: "linear-gradient(135deg,#f5f5f4 0%,#e7e5e4 50%,#fafaf9 100%)", desc: "Classic & timeless" },
  { id: "Oil Painting",       icon: "◈", preview: "linear-gradient(135deg,#fdf4ff 0%,#fce7f3 50%,#fff1f2 100%)", desc: "Rich & textured" },
];

export const BACKEND = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND}/api`;

export const resolveImage = src => (src && src.startsWith("/api/") ? `${BACKEND}${src}` : src);

export const themes = [
  { name: "Moonlit Forest",  id: "Hutan Cahaya Bulan", icon: "✦", color: "lavender" },
  { name: "Ocean Explorer",  id: "Penjelajah Laut",    icon: "≈", color: "blue" },
  { name: "Dinosaur Valley", id: "Lembah Dinosaurus",  icon: "◈", color: "coral" },
];

export const storyLanguages = [
  { code: "en", label: "English",           flag: "🇬🇧" },
  { code: "id", label: "Bahasa Indonesia",  flag: "🇮🇩" },
];

export const COVER_THEMES = {
  "Moonlit Forest":  { bg: "linear-gradient(155deg,#0f0c29 0%,#302b63 55%,#1a3a2a 100%)", spine: "#09071c", accent: "#c4b5fd", star: "✦", emoji: "🌙" },
  "Ocean Explorer":  { bg: "linear-gradient(155deg,#0c4a6e 0%,#0284c7 55%,#0e7490 100%)", spine: "#082e45", accent: "#7dd3fc", star: "≈", emoji: "🌊" },
  "Dinosaur Valley": { bg: "linear-gradient(155deg,#14532d 0%,#15803d 55%,#713f12 100%)", spine: "#0a321b", accent: "#86efac", star: "◈", emoji: "🦕" },
};

