# Kids Storybook — PRD

## Problem
Personalized digital children's book platform. Parents upload a photo of their child,
generate a custom illustrated storybook using the child's likeness, and can order a
high-quality physical printed copy.

## Personas
- Parent (primary): creates stories, orders prints, tracks shipping.
- Child (secondary): reads the finished storybook.
- Admin (internal): manages print orders and shipping statuses.

## Core requirements (from user)
- Landing page with clear "Create a Book" and "Order a Printed Copy" CTAs.
- Onboarding wizard: name, age, personality, photo, theme, story language.
- Real AI: text via LLM, illustrations via image-gen using the child's photo as reference.
- Digital flipbook viewer with page navigation.
- Print checkout: format (Hardcover/Softcover), shipping details, real payment.
- User dashboard: past stories + order status.
- Admin panel: incoming orders, update production/shipping status.
- Bilingual UI + story text: English (default), Bahasa Indonesia.

## What's implemented (as of 2026-02)
- Full React + FastAPI + MongoDB stack.
- Landing / create wizard / digital flipbook / real checkout / dashboard / admin — done.
- Bilingual UI (English + Bahasa Indonesia) — done.
- **Real AI wired**: Gemini Flash (story text) + Gemini Nano Banana (illustrations),
  via `emergentintegrations` + `EMERGENT_LLM_KEY`.
- **AI Image Gen dual-provider fallback**:
  - Primary: Google AI Pro (`GEMINI_API_KEY`, `google-genai` SDK, `gemini-2.0-flash-exp`).
  - Fallback: Emergent LLM Key (`emergentintegrations`, `gemini-3.1-flash-image-preview`).
  - If Google fails (quota, billing, network), Emergent is tried automatically.
  - Activate primary by enabling billing on Google AI Studio.
- Illustrations saved to disk under `/app/backend/generated_images/` served via `/api/images/*`.
- Narration audio saved to `/app/backend/generated_audio/` served via `/api/audio/*`.
- Read-aloud narrator (OpenAI TTS, voice "nova") per page, auto-play + auto-advance.
- "Sample Peek" auto-cycling demo on landing page (narrator-demo-01 story).
- **Dual payment gateway (LIVE)**:
  - **Stripe** (Flow B, `sk_test_emergent`): for all non-Indonesia countries.
    Redirect to hosted Stripe Checkout. Webhook at `/api/webhook/stripe`.
  - **Midtrans** (production VT- keys): for Indonesia customers.
    Snap popup. Notification at `/api/payments/midtrans/notification`.
  - Country detected by dropdown in checkout form.
  - Prices: Hardcover $34 / Rp 549,000; Softcover $22 / Rp 359,000.
  - Payment status polling: `GET /api/payments/status/{order_id}`.
  - Success page at `/checkout/success`, Cancel page at `/checkout/cancel`.

## Backlog (prioritized)
- **P0** — Enable Google AI billing so image generation via `GEMINI_API_KEY` works
  (text already works; once billing is on, Google AI Pro is the primary illustrator
  with Emergent as automatic fallback — no code change needed).
- **P1** — Parent Accounts / auth so stories & orders tie to a logged-in user.
- **P1** — Story generation as async job with polling (avoid ingress timeouts).
- **P2** — Refactor `App.js` monolith into `/pages/` directory structure.
- **P2** — More unique illustrations per book (16 / 32) once budget allows.
- **P2** — Voice Picker: let parents choose narrator voice (Nova, Onyx, Shimmer).
- **P3** — Highlight-As-Read: softly highlight each sentence as narrator reads it.

## Known constraints / notes
- Story generation is synchronous, 25–60 s. Frontend sets 180 s timeout.
- 24 pages of text, 8 unique illustrations (each shared across 3 pages).
- Google AI image generation blocked on free tier (0 quota). Text works.
  Use EMERGENT_LLM_KEY for images via emergentintegrations.
- Stripe uses `sk_test_emergent` (Emergent proxy). User needs to claim their
  sandbox via the Payments tab to go live.
- Midtrans uses production VT- keys — fully live for Indonesian customers.
