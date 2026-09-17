# Kids Storybook — PRD

## Problem
Personalized digital children's book platform. Parents upload a photo of their child,
generate a custom illustrated storybook using the child's likeness, and can order a
high-quality physical printed copy.

## Personas
- Parent (primary): signs in, creates stories, orders prints, tracks shipping.
- Child (secondary): reads the finished storybook.
- Admin (internal): manages print orders and shipping statuses.

## Core requirements (from user)
- Landing page with clear "Create a Book" and "Order a Printed Copy" CTAs.
- Onboarding wizard: name, age, personality, photo, theme, story language.
- Real AI: text via LLM, illustrations via image-gen using the child's photo as reference.
- Digital flipbook viewer with page navigation.
- Print checkout: format (Hardcover/Softcover), shipping details, real payment.
- User dashboard: past stories + order status (filtered to signed-in parent).
- Admin panel: incoming orders, update production/shipping status.
- Bilingual UI + story text: English (default), Bahasa Indonesia.
- Parent Accounts: Google Sign-In via Emergent OAuth.

## What's implemented (as of 2026-08-25)
- **Anonymous-first Create flow (2026-09-17) — DONE**:
  - `/create` is now PUBLIC (removed `ProtectedRoute`). Logged-out parents can fill the entire wizard (name, age, personality, world, story idea, visual style, photo, language) before signing in.
  - On submit while logged out, the full form (incl. photo) is stashed in `localStorage` under `idsb_pending_story` and the parent is sent to `/login`. Large photos are auto-downscaled to fit storage quota.
  - `Login.jsx` shows a contextual "Almost there! Your book details are saved…" message when a pending book exists.
  - After Google sign-in, `AuthCallback.jsx` detects the pending book and routes back to `/create`, where a resume effect restores the form and auto-starts generation.
  - Because the resumed `POST /api/stories` carries the session cookie, `get_optional_user` links the story to the new account (appears in the dashboard library). No backend change required.

- **Dedicated Cover Page (2026-08-25) — DONE & TESTED**:
  - Backend `run_story_generation()` generates a unique AI cover: `cover_title` (poetic, story-specific) + `cover_prompt` (cinematic full-page illustration prompt), both produced by the LLM alongside story text.
  - Cover illustration generated in parallel with story illustrations (no extra latency). Saved as `story.cover = {title, image}` in MongoDB.
  - Frontend `Storybook.jsx` shows cover as page 0 (`hasCover = Boolean(story.cover?.image)`), full-bleed image with gradient overlay, poetic title, child name, and brand footer.
  - PDF download opens with the cover page (dark background + illustration + title). Story pages follow as pages 1–N.
  - All 12 acceptance criteria verified by testing agent (iteration_20).


- **Photo Quality Nudges (2026-09-01) — DONE & TESTED**:
  - Live circular thumbnail preview inside the upload box after a photo is selected.
  - Upload box transitions from dashed (empty) to solid purple border (`upload-box--filled`) when filled, with "Tap to change photo" hint.
  - Three persistent photo quality tip chips below the upload box: Good lighting · Front-facing · Clear face, no shades (bilingual EN/ID).
  - Updated photo hint text to "JPG or PNG · under 10 MB".


  - Optional `story_prompt` textarea in the create form (300 char limit, live counter).
  - Positioned between theme picker and visual style picker.
  - When provided, the LLM receives a "Parent's special story idea / direction" block, making it the heart of the story.
  - Fully backward-compatible — existing stories without a prompt are unaffected.
- **Background Story Generation (P1) — DONE**:
  - `POST /api/stories` now returns immediately (< 2s) with `status: "processing"`.
  - `run_story_generation()` FastAPI BackgroundTask runs full AI pipeline (text → illustrations → audio).
  - Updates DB to `status: "completed"` or `status: "failed"` when done.
  - Frontend `Create` component shows animated progress screen with 4-step indicators and polling every 3s.
  - `Storybook` viewer has guards for `status: "processing"` and `status: "failed"` to prevent crashes.
- Full React + FastAPI + MongoDB stack.
- Landing / create wizard / digital flipbook / real checkout / dashboard / admin — done.
- Bilingual UI (English + Bahasa Indonesia) — done.
- **Real AI wired**: Gemini Flash (story text) + Gemini Nano Banana (illustrations),
  via `emergentintegrations` + `EMERGENT_LLM_KEY`.
- **AI Image Gen dual-provider fallback**:
  - Primary: Google AI Pro (`GEMINI_API_KEY`, `google-genai` SDK, `gemini-2.0-flash-exp`).
  - Fallback: Emergent LLM Key (`emergentintegrations`, `gemini-3.1-flash-image-preview`).
  - Activate primary by enabling billing on Google AI Studio.
- Illustrations saved to disk under `/app/backend/generated_images/` served via `/api/images/*`.
- Narration audio saved to `/app/backend/generated_audio/` served via `/api/audio/*`.
- Read-aloud narrator (OpenAI TTS, voice "nova") per page, auto-play + auto-advance.
- "Sample Peek" auto-cycling demo on landing page.
- **Dual payment gateway (LIVE)**:
  - Stripe (Flow B, `sk_test_emergent`): all non-Indonesia countries.
  - Midtrans (production VT- keys): Indonesia customers.
  - Country selector in checkout. Webhook + notification endpoints live.
- **Parent Accounts — Google Sign-In (Emergent-managed OAuth)**:
  - Login page at `/login` with Google Sign-In button.
  - AuthCallback handles `#session_id=` hash from OAuth.
  - Sessions stored in MongoDB `user_sessions` (httpOnly cookie, 7-day expiry).
  - Protected routes: `/create`, `/checkout`, `/dashboard` require auth.
  - Public routes: `/`, `/storybook/:id`, `/admin`.
  - Stories + orders filtered by `user_id` for dashboard.
  - Admin panel calls `/api/admin/orders` (no auth, returns all orders).
  - Logout invalidates session via cookie or Bearer header.

## Key API Endpoints
- POST /api/auth/session — exchange OAuth session_id for persistent session + cookie
- GET /api/auth/me — return current user (cookie or Bearer)
- POST /api/auth/logout — invalidate session
- POST /api/stories — create story (optional auth, attaches user_id)
- GET /api/stories — user's stories (requires auth)
- GET /api/stories/:id — public
- POST /api/orders — create order + initiate payment (optional auth)
- GET /api/orders — user's orders (requires auth)
- GET /api/admin/orders — all orders (no auth, admin view)
- PATCH /api/orders/:id — update order status (admin)
- POST /api/webhook/stripe — Stripe payment webhook
- POST /api/payments/midtrans/notification — Midtrans notification
- GET /api/payments/status/:order_id — poll payment status

## Backlog (prioritized)
- **P0** — ~~Enable Google AI billing~~ **DONE**: Updated Google AI image model from deprecated `gemini-2.0-flash-exp` to `gemini-3.1-flash-image`. Photo-referenced illustrations now generate via `GEMINI_API_KEY` as primary, with Emergent LLM Key as fallback.
- **P2** — Expand Theme Picker: add Space Explorer, Fairy Kingdom, Undersea City themes.
- **P2** — Voice Picker: let parents choose narrator voice (Nova, Onyx, Shimmer).
- **P3** — Highlight-As-Read: softly highlight each sentence as narrator reads it.

## Known constraints / notes
- Story generation is a background task (~60–90s). Frontend polls every 3s. No timeout risk.
- 24 pages of text, 8 unique illustrations (each shared across 3 pages).
- Stripe uses `sk_test_emergent` (Emergent proxy). User needs to claim sandbox to go live.
- Midtrans uses production VT- keys — fully live for Indonesian customers.
- MongoDB collections: users, user_sessions, stories, orders.
- CORS: locked to FRONTEND_URL env var (not wildcard) to support httpOnly cookies.

## Code Architecture (current — post-refactor 2026-08)

```
/app/frontend/src/
├── App.js                      # Router + providers only (47 lines)
├── App.css / Language.css      # Global styles
├── i18n.js                     # Bilingual translations (EN/ID)
├── context/AuthContext.js      # AuthProvider + useAuth
├── lib/constants.js            # API, themes, BOOK_PRICES, helpers
├── components/
│   ├── Shell.jsx               # Nav, UserMenu, LanguagePanel
│   ├── ProtectedRoute.jsx      # ProtectedRoute + AdminRoute
│   ├── CoverPreview.jsx
│   ├── StylePicker.jsx
│   └── SamplePeek.jsx
└── pages/
    ├── Home.jsx, Create.jsx, Storybook.jsx
    ├── Checkout.jsx, CheckoutSuccess.jsx, CheckoutCancel.jsx
    ├── Dashboard.jsx, Admin.jsx, Login.jsx, AuthCallback.jsx
```

