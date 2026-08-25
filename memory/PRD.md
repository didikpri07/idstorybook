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
- Print checkout: format (Hardcover/Softcover), shipping details.
- User dashboard: past stories + order status.
- Admin panel: incoming orders, update production/shipping status.
- Bilingual UI + story text: English (default), Bahasa Indonesia.

## What's implemented (as of 2026-02)
- Full React + FastAPI + MongoDB stack (Feb 2026).
- Landing / create wizard / digital flipbook / mocked checkout / dashboard / admin — done.
- Bilingual UI (English + Bahasa Indonesia) — done.
- **Real AI wired**: Gemini 3 Flash (32-page story text) + Gemini Nano Banana
  (8 illustrations, child photo used as reference for character likeness),
  via `emergentintegrations` + `EMERGENT_LLM_KEY`.
- Illustrations saved to disk under `/app/backend/generated_images/` and served via
  `/api/images/*` static mount (keeps Mongo documents small).
- Local pastel placeholder image served when an illustration call fails.
- Partial-failure signal: story includes `illustrations_generated` /
  `illustrations_expected` and `status: "ready" | "partial"`.
- Generic client error message (no upstream billing text leaked).
- Stripe checkout — **MOCKED** (order is stored but no real payment session).

## Backlog (prioritized)
- **P0** — Enable real Stripe test-mode checkout (`/api/orders` → Stripe session +
  webhook, replacing current mock).
- **P1** — Parent Accounts / auth so stories & orders tie to a logged-in user.
- **P1** — Story generation as async job with polling (avoid ingress timeouts
  during peak load; today it's a 25–60s synchronous request).
- **P2** — Read-aloud / TTS narration per page.
- **P2** — More unique illustrations per book (16 / 32) once budget / speed allow.
- **P2** — Refactor `App.js` into per-route page components.

## Known constraints / notes
- Story generation is synchronous and takes 25–60 s. Frontend sets a 180 s timeout.
- 32 pages of text, 8 unique illustrations (each shared across 4 pages) — deliberate
  trade-off for cost & latency.
- Requires `EMERGENT_LLM_KEY` in `/app/backend/.env`; user needs enough balance —
  budget-exhausted errors surface as a friendly 502 message.
