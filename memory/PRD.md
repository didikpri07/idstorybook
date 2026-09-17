# IDStorybook — Feature Expansion (Phase 2)

## Original problem statement
Build on the existing IDStorybook codebase (React + Tailwind frontend, FastAPI backend, MongoDB) to add the four highest-impact features for user retention and experience.

### What Already Exists (No Changes)
- AI story generation with per-page illustrations + narration
- Selectable book length (8/16/24/32)
- Digital storybook viewer, PDF download
- Physical book checkout (Stripe test mode + Midtrans stubs)
- Photo upload with quality tips
- Dashboard library, order tracking, admin panel
- Bilingual EN/ID

### New Features to Build (Prioritized)
**Feature 1: Parent Accounts & Authentication**
- Email/password signup + login (JWT-based)
- Google OAuth as a second option (many Indonesian parents use Google)
- Each parent gets a private library — stories are tied to their account
- Guest mode preserved: unauthenticated users can still create one story, but prompted to sign up to save it
- "My Library" dashboard becomes auth-gated; shows only that parent's stories and orders
- Password reset via email (SendGrid or Resend)
- Edge case: existing stories in MongoDB have no `user_id` — migration script to mark them as "legacy/guest" so they don't break

**Feature 2: Live Generation Progress**
- Backend: switch story generation to a background task (FastAPI BackgroundTasks or a simple polling model)
- New endpoint: `GET /api/stories/{story_id}/progress` returns `{ status: "generating", current_page: 5, total_pages: 32, stage: "illustrating" }`
- Backend updates progress in MongoDB as each page's text, illustration, and narration complete
- Frontend: replace the static loading spinner with a progress screen showing "Writing page 5 of 32...", "Illustrating page 12 of 32...", animated progress bar, estimated remaining time based on ~13s/page
- Poll every 3 seconds; switch to reader when status = "complete"
- If generation fails mid-way (timeout, 429), mark story "partial"; show completed pages and "Retry remaining pages"

**Feature 3: Voice Picker**
- Add "Narrator Voice" selector alongside length/theme
- Nova (warm), Onyx (deep), Shimmer (soft), or supported provider equivalents
- Pass voice ID to backend/TTS; default Nova; store voice in story
- Bilingual "Narrator Voice" / "Suara Narator"; previews optional

**Feature 4: Highlight-As-Read (Sentence-Level)**
- Sentence-level only, not word-level
- Split page text into sentences; estimate timing proportionally by sentence character count and actual audio duration
- Store `[{ sentence: "...", start_ms: 0, end_ms: 3200 }, ...]` beside audio URL
- Match `timeupdate` playback position to ranges; soft yellow highlight
- Legacy stories without timestamps play without highlighting
- Sentence tap seeking is optional if straightforward

### Tech stack requested
React CRA/CRACO + Tailwind; FastAPI; MongoDB; PyJWT, bcrypt; Google OAuth authlib; Resend/SendGrid; existing TTS.

### Requested implementation order
1. Parent accounts: models, signup/login/Google/reset routes, JWT protection and ownership, legacy migration, auth context/pages/protection, guest save, library filtering.
2. Generation progress: page checkpoints, progress API, partial failure, animated polling display, auto-reader, retry.
3. Voice: payload, TTS parameter, persisted choice, bilingual picker; preview optional.
4. Highlight: duration-derived sentence timings, playback matching, yellow fade, legacy fallback.

### Assumptions and exclusions
Sentence estimates suffice; forced alignment out of scope. Only Google social login. Stripe stays test mode. No signup email verification in v1. Apple sign-in, account deletion, and live payments deferred.

## User choices / source
- Prepare password-reset integration now; credentials later. Resend selected as preparation default.
- Google OAuth via authlib using existing credentials if configured; user will supply client ID/secret. No credentials were found in workspace or source ZIP.
- Use user's direct Google AI key, not the universal key. Key stays in backend `.env`, never here.
- Defer account deletion. User also requested pricing advice.
- Workspace initially contained a starter only. User explicitly chose to provide the existing code instead of rebuilding.
- Source uploaded twice: `idstorybook-17sept-on-nurfitiannagitchu.zip`. Restored first archive; original theme and existing product pages retained.

## Personas
- Indonesian/English-speaking parents creating personalized stories, saving a family library and ordering books.
- Guest parent making one trial story and claiming it on registration/login.
- Studio admin tracking print orders; original access-controlled admin preserved.

## Architecture decisions
- Preserve original Fredoka/Outfit, lavender/coral/teal visual system; additive `Phase2.css`, no redesign.
- Protected environment values unchanged. One shared Motor connection (`database.py`).
- `accounts.py`: JWT in secure HttpOnly SameSite=Lax cookie, optional bearer token for API, revocable JTI sessions, bcrypt passwords, password version rotation, legacy DB-session support.
- Private story GET, progress, retry and order endpoints require owner or matching random guest cookie; no legacy owner inference. Public sharing is explicit, read-only, random capability link.
- Guest quota enforced per browser cookie using unique MongoDB guest index. Cookie clearing/new browser cannot be prevented without stronger identity.
- Guest stories auto-claimed atomically after successful signup/login; explicit claim endpoint is idempotent.
- Authlib OIDC state/nonce via secure signed session. Google disabled until configured. Resend disabled truthfully until configured. Never simulate successful login/email delivery.
- Reset token stored only as hash within user record with expiry; atomic one-time reset increments auth version and removes all sessions. Rate limits persisted by hashed identifiers.
- `generation.py`: sequential background tasks with MongoDB checkpoints; stores draft and photo privately until completion; retains finished assets on retry. Service restart marks interrupted stories partial.
- Stages: writing, illustrating_cover, illustrating, narrating, complete. Statuses generating/partial/complete; old processing/failed/completed normalized by progress API.
- Direct Google text `gemini-3-flash-preview`, images `gemini-3.1-flash-image`, TTS `gemini-3.1-flash-tts-preview`, environment-configurable.
- Stable aliases `nova → Sulafat`, `onyx → Algenib`, `shimmer → Achernar`. UI displays actual Google voice names. Legacy narrator label remains untouched.
- Actual WAV/MP3 duration measured with mutagen; sentences allocated duration by character count. Reader supports highlighting and tap-to-seek; legacy narration remains playable.
- Existing print checkout preserved except ownership protection and trusted redirect origin. Prices not changed.

## Implemented — 2026-09-17
- Imported supplied frontend/backend/media without overwriting environment/dependency configuration.
- Email/password accounts, private library and order filtering, guest claim, migration, reset preparation, authlib Google preparation.
- Durable generation progress, retry and interrupted-job recovery; 3-second polling and auto-reader.
- Three Google voices with persisted choice and bilingual labels.
- Sentence timing, yellow highlighting, seeking, legacy fallback.
- Ownership-aware explicit sharing; original PDF/checkout/admin flows retained.
- Fixed existing dashboard references to missing translation keys; responsive account and reader layout extensions.
- Verified production React build and creation/signup screens. Direct Google key/model accepted; real text, cover, illustration and Algenib narration produced successfully.
- Discovered mutagen objects without tags are falsey despite valid audio; fixed duration check to use `is None`. Full testing pending at time of this entry.
- Live retry completed all eight pages, preserving existing assets. Browser email login, private library, real read-aloud and active sentence highlighting verified.
- Exact trusted-origin allowlist includes the preview ingress's observed canonical alias; no wildcard CSRF allowlist. Browser sign-in regression fixed and verified.
- First test report `/app/test_reports/iteration_1.json`: 12 backend regression tests passed, frontend auth/reader/390px overflow checks passed. Google and Resend success paths remain pending real credentials. Duplicate legacy me/logout routes removed per report. Focused recovery tests pending.

## Testing notes
- QA generated story: `e62b417b-03b1-4278-99a7-3e4c5d00d386` (8 pages, Maya, English, Algenib). First pass stopped after first audio due to fixed duration check.
- Ephemeral `/tmp` cookie files were lost during environment restart. This QA story ONLY was assigned directly to the newly created QA parent so its retry/checkpoint path can be verified. This is test-fixture setup, not a product guest-claim test.
- Durable local test credentials and cookies: `/root/storybook-tests/`; do not commit credentials.
- No application AI output is mocked. Provider failures result in partial status. Test-only doubles may be used for deterministic timeout/429 assertions.

## Prioritized backlog / next tasks
P0: No unresolved implementation blockers in the four core flows. Optional provider success paths remain dependent on credentials below.
P1 external setup: User supplies Google OAuth client ID/secret; callback must match backend environment. User supplies Resend key + verified sender; then verify real reset email delivery and Google callback.
P1: Validate printing unit costs and generation costs before committing retail pricing. No live payment activation in this phase.
P2: Optional voice-preview snippets, account deletion, email verification, distributed job queue at higher volume, stronger anonymous abuse protection.

## Pricing guidance requested (not a price change)
Initial hypothesis: digital single book Rp49,000–79,000; longer books priced higher only after measured provider costs. Keep original print prices until printer, packaging, shipping and support costs are confirmed. Prefer pay-per-book initially; consider a three-book bundle once repeat demand is measured. These are testing hypotheses, not verified market prices or guaranteed margins.

## Final verification and fixes — 2026-09-17
- `/app/test_reports/iteration_2.json` focused tests: deterministic timeout/audio-failure recovery retains checkpoints and retries missing work only; concurrent retries launch once, non-owner denied, complete/generating retry409. Actual migration executed and idempotent. Real Google Sulafat EN and Achernar ID tiny narration probes passed in addition to full Algenib book.
- Final regression run: 21/21 tests pass (`/app/test_reports/pytest/pytest_results_final.xml`); frontend production build passes. Test-only provider doubles are confined to tests; application generation is real.
- Browser verified guest-save signup/claim and isolation, legacy audio without timestamps, bilingual controls, 390px layouts and 32-page dot wrapping. Downloaded real book PDF is nonempty with9 pages (cover+8).
- Fixed payment regression: shell-provided Stripe test key was not inherited by supervisor; setup script copies it privately to backend environment. Actual `/api/orders` now creates Stripe test checkout successfully (200 with checkout URL). Midtrans credentials missing; config endpoint and UI disclose unavailable state and API returns503 before inserting an order. No real payment was charged or activated.
- Fixed existing checkout missing translation references and layout class mismatches, without changing products/prices.
- Fixed manual page-turn stale highlight by pausing/resetting playback; automatic audio-ended page turns still read the next page. Audio element keyed per page prevents previous-page events affecting the next page.
- Sentence seek-before-first-play uncovered original Starlette static serving lacked byte-range support. Added `audio_routes.py` supporting GET/HEAD/206 byte ranges/416 invalid ranges, preserving WAV/MP3 media routes. Verified external Range bytes100-199 returns206 and100bytes. Final browser check: initial second-sentence seek lands at4s, manual page clears highlighting/pauses at0, automatic next page starts narration correctly.
- Added exact-origin config docs, private local QA fixture docs, environment/archive ignores. No provider secrets included in PRD/reports.
- Remaining verification limitation: controlled progress fixtures sometimes reached their terminal state before browser captured the initial generating view. Backend progress/race/checkpoint tests pass; generating UI and terminal partial/reader states were verified individually. Google callback and real reset email delivery are not verified because credentials intentionally deferred. Full paid Stripe settlement/webhook completion not exercised; test checkout session creation verified.

## Next action list
1. Supply Google OAuth Web client ID/secret; register exact `GOOGLE_OAUTH_REDIRECT_URI`; verify Google login end-to-end.
2. Supply Resend API key and verified sender/domain; verify real password-reset email delivery.
3. Supply Midtrans server/client settings when Indonesian print checkout is needed (existing provider integration retained).
4. Collect AI usage and printer/fulfilment quotes; validate proposed digital prices and test a three-book bundle. Current app print prices unchanged.
5. Later: account deletion, email verification, voice previews, distributed background-job worker/leases, stronger cross-browser guest abuse controls.