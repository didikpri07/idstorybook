// Tab-local drafts survive signup/login without uploading a child's photo anonymously.
const DRAFT_KEY = 'idsb_story_draft_v1';
const MAX_DRAFT_AGE = 2 * 60 * 60 * 1000;

export const DEFAULT_STORY_FORM = {
  child_name: '', age: 5, gender: '', theme: 'Moonlit Forest',
  visual_style: 'Classic Watercolor', photo_base64: '', story_language: 'en',
  story_prompt: '', page_count: 24, voice_id: 'nova',
};

export function readStoryDraft() {
  try {
    const draft = JSON.parse(sessionStorage.getItem(DRAFT_KEY) || 'null');
    if (!draft || !Number.isFinite(draft.savedAt) || Date.now() - draft.savedAt > MAX_DRAFT_AGE || !draft.form) {
      sessionStorage.removeItem(DRAFT_KEY);
      return null;
    }
    const form = { ...DEFAULT_STORY_FORM };
    for (const key of Object.keys(form)) {
      const value = draft.form[key];
      if (typeof value === 'string' || typeof value === 'number') form[key] = value;
    }
    if (![8, 16, 24, 32].includes(Number(form.page_count))) form.page_count = 24;
    if (!['nova', 'onyx', 'shimmer'].includes(form.voice_id)) form.voice_id = 'nova';
    if (!['en', 'id'].includes(form.story_language)) form.story_language = 'en';
    return { form, photoName: typeof draft.photoName === 'string' ? draft.photoName : '' };
  } catch {
    return null;
  }
}

export function saveStoryDraft(form, photoName) {
  // Fail visibly if storage is blocked/full; never discard the selected photo silently.
  sessionStorage.setItem(DRAFT_KEY, JSON.stringify({ form, photoName, savedAt: Date.now() }));
}

export function clearStoryDraft() {
  try { sessionStorage.removeItem(DRAFT_KEY); } catch { /* Storage can be unavailable. */ }
}

export function prepareStoryPhoto(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      try {
        const scale = Math.min(1, 1024 / Math.max(image.width, image.height));
        const canvas = document.createElement('canvas');
        canvas.width = Math.max(1, Math.round(image.width * scale));
        canvas.height = Math.max(1, Math.round(image.height * scale));
        const context = canvas.getContext('2d');
        context.fillStyle = '#ffffff';
        context.fillRect(0, 0, canvas.width, canvas.height);
        context.drawImage(image, 0, 0, canvas.width, canvas.height);
        resolve(canvas.toDataURL('image/jpeg', 0.85));
      } catch (error) { reject(error); }
      finally { URL.revokeObjectURL(url); }
    };
    image.onerror = () => { URL.revokeObjectURL(url); reject(new Error('Invalid photo')); };
    image.src = url;
  });
}