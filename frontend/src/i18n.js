import { useEffect, useState } from "react";

export const languages = [
  { code: "en", label: "English", flag: "🇬🇧" },
  { code: "id", label: "Bahasa Indonesia", flag: "🇮🇩" },
];

export const copy = {
  en: { library: "My library", orders: "Orders", interface: "Interface", storybook: "Storybook", language: "Language", choose: "Choose language" },
  id: { library: "Perpustakaan saya", orders: "Pesanan", interface: "Antarmuka", storybook: "Buku cerita", language: "Bahasa", choose: "Pilih bahasa" },
};

export function useLanguage() {
  const [language, setLanguage] = useState(() => window.localStorage.getItem("kids-storybook-ui") || "en");
  useEffect(() => {
    window.localStorage.setItem("kids-storybook-ui", language);
    document.documentElement.lang = language;
    window.dispatchEvent(new CustomEvent("kids-storybook-language", { detail: language }));
  }, [language]);
  return { language, setLanguage, text: copy[language] };
}

export function getStoryLanguage() {
  return window.localStorage.getItem("kids-storybook-story") || "en";
}