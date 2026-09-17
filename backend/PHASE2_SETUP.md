# Phase 2 configuration

Keep all existing environment values. Do not place API keys in frontend code.
`TRUSTED_FRONTEND_ORIGINS` is an exact comma-separated allowlist for CORS and write-origin validation. The current environment's public URL and observed canonical ingress origin are configured; never replace this with a wildcard.

## Google sign-in
Set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_OAUTH_REDIRECT_URI` in backend `.env`. Create a Google OAuth Web Application, configure consent/test users as appropriate, and register the exact redirect URI from the environment (`/api/auth/google/callback`). Set `OAUTH_STATE_SECRET` to a long random secret. Existing managed-session exchange remains supported for backward compatibility.

## Password reset (Resend)
Set `RESEND_API_KEY` and `RESEND_FROM_EMAIL` using a verified sender/domain. Reset emails return to `FRONTEND_URL/reset-password`. Tokens expire after 30 minutes and may be used once. Missing configuration returns 503 and is disclosed in the UI; no emails are simulated.

## Google AI
`GEMINI_API_KEY` is the user's direct Google AI Studio key. Models use `GEMINI_TEXT_MODEL`, `GEMINI_IMAGE_MODEL`, and `GEMINI_TTS_MODEL`. Voice aliases are nova/Sulafat, onyx/Algenib, shimmer/Achernar. No universal key is required. Actual duration is parsed from audio; sentence timings are approximate, not forced alignment.

## Accounts and jobs
Keep `JWT_SECRET` stable and private. Rotating it expires JWT sessions. MongoDB stores bcrypt password hashes and password-reset digests, not plaintext credentials. JWTs are checked against revocable sessions. Cookies require HTTPS.

Run `python migrate_legacy.py` from the backend directory to tag ownerless records; startup also runs this idempotently. It never assigns old books to a parent or makes them public. Interrupted jobs become partial after process restart. Retrying resumes their saved draft and assets. A job queue/multi-worker lease is a later scaling improvement.

## Pricing worksheet
Suggested initial experiments, NOT verified production pricing:
- 8-page digital story: Rp49,000.
- 16-page digital story: Rp69,000.
- 24/32-page story: only price after measuring AI and support costs; test Rp89,000–119,000 if margins support it.
- Printed books: retain existing Rp359,000 softcover / Rp549,000 hardcover until quotes are known. Separate shipping and confirm taxes.

Minimum viable price = total variable cost / (1 - target gross margin). Example only: Rp20,000 variable cost at 65% target margin needs approximately Rp57,200 revenue before applicable taxes. Include text, images, TTS, failed retries, payment fees, storage, and support in digital costs; add printing, packaging, fulfilment and shipping for physical books. A three-book bundle is a better first retention experiment than unlimited generation.