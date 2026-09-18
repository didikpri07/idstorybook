# Regional pricing and payment setup

## Current modes
- Indonesia: Midtrans PRODUCTION (`MIDTRANS_IS_PRODUCTION=true`), hosted Snap checkout.
- Other countries: existing Stripe TEST adapter. `STRIPE_API_KEY` remains the configured test key. The supplied live **publishable** key is stored separately as `STRIPE_LIVE_PUBLISHABLE_KEY` and is not used with the test server key.
- Gemini uses the supplied direct server-side key unchanged.
- Keys belong only in backend `.env`, excluded from source control. No secret values are in this document or browser bundles.

## Midtrans notification setting (merchant dashboard)
Set Payment Notification URL to the configured `FRONTEND_URL` plus `/api/payments/midtrans/notification`.
Current external endpoint: `https://storybook-expansion.preview.emergentagent.com/api/payments/midtrans/notification`.
The return URL is supplied on each checkout (`/checkout/success?order_id=...`). Browser polling additionally verifies status with Midtrans, so a missing/delayed notification never creates a false success. Configure notifications so paid books can begin even when the browser is closed.

## Stripe test checkout
Existing adapter configures its authenticated gateway. Integer USD cents are sent through the adapter-configured SDK, preserving request idempotency, metadata, and test/live verification.
Webhook path: `/api/webhook/stripe`. If `STRIPE_WEBHOOK_SECRET` is supplied, signature verification is enabled. Without it, posted events are only lookup triggers: authoritative server retrieval must confirm amount, currency, metadata, completed status and test mode before any entitlement is granted.
Checkout does not add new tax/shipping fees in this phase; quoted totals match the requested tables. No automatic tax calculation/filing integration was added. Stripe real-payment activation remains outside this task.

## Admin access
`ADMIN_EMAILS` contains the user-designated admin address. It is reserved, not publicly self-registrable as an administrator. `scripts/bootstrap_admin.py` created a password-setup token with a24-hour lifetime; its private link is in `/root/storybook-tests/admin_setup.json`. Password setup is one-use via the existing reset-password screen. It is not emailed because email delivery is still unconfigured. Never publish that file or token.
After setting a password, sign in and open `/admin/pricing`. Update both regional tables there. Prices persist in MongoDB; old orders retain their original version/amount. Optimistic version checking prevents two admins overwriting each other's changes. An audit record captures each revision.

## Free-book policy
- Signup/sign-in is required before any generation.
- Each account receives one8-page digital book free. Longer books remain paid and do not consume the free8-page entitlement.
- A prior generated/partial8-page free book counts toward the allowance. Existing books are never charged retroactively.
- Reserve the allowance atomically before spending AI calls. If generation pauses, retry that same book for no extra payment; do not create another free book. Reservation is released only if initial story insertion fails before generation.
- New paid books stay `awaiting_payment` with no AI activity. Verified payment atomically authorizes and starts one generation task. Pending/failed/fraud-review payments do not generate books.
- PDFs are always downloadable free from already-generated stories. Print is an additional purchase at the page-length/format price; no credit is deducted for the digital purchase.

## Country detection
Backend calls `COUNTRY_API_URL` with the visitor's public IP, caches only a hash+country for up to an hour, and does not store precise location. Manual Indonesia/Other correction is always available and remembered in the browser. If lookup fails, users choose manually. Country is a pricing preference, not identity/fraud proof.

## Production-safe verification
Read-only Midtrans validation used GET status for a known-nonexistent order and returned provider404 (credentials accepted). No Midtrans live transaction or charge was made during this check. Test doubles for settlement/signature/race tests are confined to isolated test processes. Do not run live Midtrans payments automatically.