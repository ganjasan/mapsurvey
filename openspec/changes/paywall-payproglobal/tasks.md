## 1. Foundation: app, models, settings

- [ ] 1.1 Create `billing/` app (apps.py, `__init__`, admin, urls, templates dir); register in `INSTALLED_APPS` after `survey`; mount `billing.urls` at `/billing/` and the org-scoped routes under `/org/<slug>/billing/` and `/org/<slug>/help/` in `mapsurvey/urls.py`
- [ ] 1.2 Models + migration: `Plan`, `Subscription` (statuses, `current_period_end`, raw date string, `ppg_*` ids, `renewal_type`, `failed_attempts`, cancellation fields, `superseded_at`, `pending_change_until`, `lapse_notified_at`), `BillingEvent` (unique `(order_id, ipn_type_id, body_sha256)`, `ignored_test`, `error`, `verified_by`), `CheckoutIntent`, `ProHelpRequest`; seed `Plan` rows `free`/`pro` in a data migration
- [ ] 1.3 Settings: `PPG_VENDOR_ACCOUNT_ID`, `PPG_SECRET_KEY`, `PPG_VALIDATION_KEY`, `PPG_API_SECRET_KEY`, `PPG_PRODUCTS` (JSON env), `PPG_ACCEPT_TEST_IPN`, `PPG_TEST_MODE`, `PPG_IPN_ALLOWED_IPS` (defaults from docs), `PPG_IPN_DOMAIN` override; `render.yaml` env vars for prod + previews (`PPG_ACCEPT_TEST_IPN`/`PPG_TEST_MODE` true in previews, secrets `sync: false`)
- [ ] 1.4 Django admin for `BillingEvent` (read-only payload, filters by type/test/error), `Subscription`, `CheckoutIntent`, `ProHelpRequest`; admin action "mark chargeback-won reviewed"

## 2. Entitlements and gates

- [ ] 2.1 `billing/features.py` registry (`unbranded`, `pro_help`) and `billing/entitlements.py::for_organization` implementing the access rule (states × period end) with a per-request cache
- [ ] 2.2 `require_feature` view decorator (403 page with upgrade link) and `has_feature` template tag; unit tests for every state/date combination in the spec (GIVEN/WHEN/THEN)
- [ ] 2.3 `survey/ai/quota.py::check_quota` reads `for_organization` (still permissive); test asserts the lookup happens
- [ ] 2.4 Nightly Celery beat task `billing.tasks.notify_lapsed`: `plan_lapsed` event + owner email (template), idempotent via `lapse_notified_at`; tests for detect/rerun

## 3. Webhooks

- [ ] 3.1 `billing/ipn.py`: parse body as raw strings, IP allow-list from `request.cf_ip`, SHA256 `SIGNATURE`, MD5 `HASH` (test → `MD5("1")`), `body_sha256` without `IS_RESENT`; port verification from `~/.claude/skills/payproglobal/scripts/ppg_ipn.py`; tests reproduce the documented MD5 examples and reject each failure mode
- [ ] 3.2 Organisation resolution chain (`x-org_id` → nonce → `SUBSCRIPTION_ID` → owner email) with `ORDER_CUSTOM_FIELDS` parser; unresolved → stored with `error`, 200
- [ ] 3.3 State machine `apply(event, subscription)` for types 1, 13, 6, 7, 8, 9, 10, 11, 2, 3, 14, 15 and the pass-through default; replacement-purchase supersede logic; `pending_change` cleared on apply
- [ ] 3.4 View `POST /billing/ipn/` (`csrf_exempt`, `require_POST`): verify → test-mode gate → `get_or_create` in a transaction → apply → `on_commit` PostHog/mail → 200; 400 on verification failure, 500 on our exception (transaction rolled back)
- [ ] 3.5 Fixtures: capture one payload per event type from the PayPro IPN simulator (preview URL), redact, store under `billing/tests/fixtures/`; pin the `SUBSCRIPTION_NEXT_CHARGE_DATE` format and the multi-field `ORDER_CUSTOM_FIELDS` encoding in a test; lenient date parser keeps the raw string
- [ ] 3.6 Integration tests: full lifecycle (charge → rebill → fail×3 → suspended → renewed → charge; charge → refund; charge → chargeback; duplicate resend; test-mode on/off; unresolved)

## 4. Checkout and return page

- [ ] 4.1 `billing/checkout.py::build_checkout_url` (products, `billing-*` prefill, `language`, `x-*` with separator guard, `ipn-domain` = `PPG_IPN_DOMAIN` or `RENDER_EXTERNAL_HOSTNAME` or request host, test-mode params, `use-company-purchase` on yearly, `quote=True` variant adding `display-quote=true&quote-mode=editable`); tests for monthly/yearly/quote and prod/preview variants and the separator guard
- [ ] 4.2 View `POST /org/<slug>/billing/checkout/` with `period` and optional `quote` (owner only, 404 when `PPG_PRODUCTS` empty): create `CheckoutIntent` (records `quote`), emit `plan_checkout_started`, redirect
- [ ] 4.3 Return page `/billing/return/` (GET+POST, csrf-exempt for the PayPro POST) + `GET /billing/return/status/?nonce=` JSON; template with 2 s polling for 60 s and fallback copy; `?pending=1` variant for PayPro's "Waiting for payment" redirect (bank-transfer copy, no polling); tests: active / pending / waiting / unknown nonce; assert no writes
- [ ] 4.4 Upgrade entry points: `org_settings.html` Billing section (plan + "Upgrade monthly 49" / "Upgrade yearly 490" / "Get a quote" for owners, link to billing page); hidden when products unconfigured

## 5. Subscription management page

- [ ] 5.1 `billing/ppg.py` API client (port of the skill's `ppg_api.py`: `suspend`, `renew`, `change_product`, `send_onetime_login_email`, `store_products`, `is_configured()`), secret stripped from logs; tests with a mocked transport incl. `isSuccess=false`
- [ ] 5.2 View `/org/<slug>/billing/` (owner/admin; 403 otherwise): plan/state/period end/renewal type (Auto vs Manual copy)/subscription id/last invoice link, "awaiting bank transfer" when the last event is `OrderOnWaiting`, "Update payment method" (`?subscr-id=`), "Manage in PayPro customer account", duplicate-subscription warning
- [ ] 5.3 Owner actions (POST, confirm step, only when `is_configured()`, else 404): cancel (reason select → `cancellationReasonId`), resubscribe, switch period, email login link; set `pending_change_until`; show API errors; tests for visibility, 404 without key, pending marker, error surfacing
- [ ] 5.4 Billing page copy: the "Cancelling and refunds" note from design.md D7 (Pro until period end → Free; refund → Free immediately; data untouched), i18n strings

## 6. Pro features

- [ ] 6.1 Branding gate: `_made_with_mapsurvey.html` evaluates `has_feature survey.organization 'unbranded'` and `survey.show_branding`; update the three includes (survey, thanks, editor thanks preview) and the public results page to pass `survey`; tests for Free/Pro×on/off and lapse
- [ ] 6.2 Survey settings: `show_branding` control enabled only with `unbranded`; disabled + "Upgrade to Pro" hint otherwise; server ignores the field without the entitlement; tests
- [ ] 6.3 Pro help channel: `ProHelpRequestForm` (kind, survey limited to the org, message ≤5000, contact), view `/org/<slug>/help/` (form for Pro members; offer page + Upgrade for Free; 403 on Free POST), Celery task sending team + confirmation mails with retry, `pro_help_requested` event; tests

## 7. Operations and rollout

- [ ] 7.1 `manage.py ppg_check`: with API → `GetStoreProducts` for `PPG_PRODUCTS` ids; without → print checkout URLs and the IPN URL to configure
- [ ] 7.2 Docs: `docs/billing.md` — control-panel checklist (products 49/490 with local prices EUR+USD and IPN URL; monthly card+PayPal only, yearly "allow users to pay with all payment methods"; Integration keys → Render; IPN URLs list with `*.onrender.com` wildcard; thank-you redirects: Fulfilled → `/billing/return/`, Waiting for payment → `/billing/return/?pending=1`; Failed-IPN notification email), the email to PayPro requesting API key + whitelist of Render outbound IPs + extended webhooks (`OrderOnWaiting`), rollback (`PPG_PRODUCTS` empty)
- [ ] 7.3 PostHog: register the six events in `product_events` docs/constants; error tracking on verification failures and unresolved events
- [ ] 7.4 `./run_tests.sh billing survey` green; `.env.ports.example` registry entry (490) committed; CLAUDE.md gets a short "Billing" section (app layout, the one grant path, how to test with the simulator)
- [ ] 7.5 Preview verification: open PR with `[render preview]`, configure IPN URLs, place a test order with test card `4532789918951515`, confirm `BillingEvent` + entitlement, run simulator for every type; record findings (date format, custom-fields encoding, wildcard match) back into design.md Open Questions
