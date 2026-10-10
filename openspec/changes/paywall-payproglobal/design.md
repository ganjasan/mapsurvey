# Design — Paywall on PayPro Global

## Context

Mapsurvey has never taken money. The free product is the trial; `/pro/` collected what
people would pay for; the answer we act on is "access to Artem" (consulting, analytics,
reports) plus an unbranded product, sold as a **Pro subscription**.

PayPro Global (PPG) is a Merchant of Record: it hosts the checkout, stores cards, charges
renewals, calculates and remits tax, issues invoices, handles chargebacks and first-line
support. Our contract with PPG has three legs — a checkout URL out, webhooks (IPN) in, and
an optional REST API. Everything we know about PPG is in the local skill
`~/.claude/skills/payproglobal` (full docs mirror, enum tables, verification formulas,
reference scripts); this document does not repeat it.

Constraints that shape the design:

- The PPG account exists but is **empty**: no products, no API secret key, no IP whitelist.
  The API needs a key issued by an account manager and Render's outbound IPs whitelisted.
  v1 must work without the API and gain it later without a redesign.
- There is no PPG sandbox. Test mode is a URL parameter + test cards; the control panel
  has an IPN simulator. Previews must receive their own webhooks (`ipn-domain`).
- The badge partial today renders unconditionally; `SurveyHeader.show_branding` exists but
  is ignored ("future paid-tier preference"). `survey/ai/quota.py::check_quota` is a no-op
  seam reserved for exactly this change.
- Organisations are the account unit (`Organization`, `Membership` roles
  owner/admin/editor/viewer). `org_settings` is owner-only. Real client IP is
  `request.cf_ip` (Cloudflare middleware). PostHog events go through
  `product_events.emit()`; mail through `survey.mail.send_templated_mail`; background work
  is Celery (`survey/tasks.py` style).
- The feature set will grow; this change ships two gated features and must make the third
  cost one line.

## Goals / Non-Goals

**Goals:**
- Take a Pro payment end to end on production and on PR previews, with every entitlement
  derived from verified webhooks and nothing else.
- One source of truth for "what may this organisation do", with a registry of features
  and two gate helpers (view decorator, template tag).
- A billing page where an owner sees status and can fix a failed payment today, and can
  cancel / resubscribe / switch period as soon as the API is unlocked — without a deploy.
- A Pro help channel that turns the service promise into a concrete request we receive.
- Operability: every webhook stored raw, replayable; admin visibility; PostHog events;
  a command that proves configured product IDs exist.

**Non-Goals:**
- Pricing page, localised prices, coupons UI, trials with card, one-time project passes,
  seats, proration of upgrades, scheduling of consulting sessions, dunning emails of our
  own (PPG sends them), invoice generation (PPG issues invoices).
- Any Pro feature beyond `unbranded` and `pro_help`.

## Decisions

### D1. A separate `billing` Django app, not more code in `survey`

`survey` is already the whole product. Billing has its own models, its own external
dependency, its own security surface (an unauthenticated POST endpoint) and its own tests.
A separate app keeps the import direction one-way (`survey` imports `billing.entitlements`;
`billing` imports `survey.models.Organization` only) and makes the webhook handler's
dependencies auditable. Rejected: a `survey/billing.py` module — it would end up importing
half of `survey` to resolve organisations and send mail, and the IPN view would share a
namespace with respondent views.

### D2. Entitlements are a pure function over our own rows; PPG is never read at request time

```
billing.entitlements.for_organization(org) -> Entitlements(plan: 'free'|'pro',
    state: 'none'|'active'|'past_due'|'cancelling'|'lapsed', until: datetime|None,
    features: frozenset[str])
```

It reads the organisation's current `Subscription` row and applies one rule:

> Pro **while `now < current_period_end`** in states `active`, `past_due`, `suspended`,
> `terminated`; **not Pro** in `finished`, `refunded`, `charged_back`, or when the period
> end has passed.

That is the access rule PPG's own docs prescribe (keep access until
`SUBSCRIPTION_NEXT_CHARGE_DATE` after suspension/termination; cut on finish/refund). No
cron is needed to "lapse" a subscription — the function compares dates — but a nightly
task emits `plan_lapsed` once and sends our own "your Pro ended" mail (PPG's mail is about
the payment, ours is about the service).

Rejected: calling `GetSubscriptionDetails` on page load or caching PPG state — adds a
network dependency to every request, needs the API we do not have, and the webhook stream
already carries every transition.

### D3. The feature registry

`billing/features.py`:

```python
FEATURES = {
    'unbranded': Feature(plans={'pro'}, label=_('Remove "Made with Mapsurvey"')),
    'pro_help':  Feature(plans={'pro'}, label=_('Consulting, analysis and reports by the Mapsurvey team')),
}
```

`Entitlements.features` is the set whose `plans` include the organisation's plan.
Gates: `@require_feature('pro_help')` for views (403 with an upgrade hint for members,
404-equivalent for outsiders handled by the existing access checks), and
`{% has_feature org 'unbranded' as unbranded %}` for templates. `check_quota` becomes
`entitlements.for_organization(org)` → no limit for any plan today, but the call site is
real so the next change only adds a number to the plan.

Rejected: boolean columns on `Organization` per feature (`is_unbranded`) — every new
feature would be a migration and the entitlement would be writable by anyone with ORM
access, decoupled from the subscription that justifies it.

### D4. Webhook handling: verify → persist → apply → 200

`POST /billing/ipn/` (`csrf_exempt`, no session):

1. **Verify** in this order, cheapest first: source IP in `PPG_IPN_ALLOWED_IPS` (read from
   `request.cf_ip`; the allow-list is a setting because PPG may add addresses); SHA256
   `SIGNATURE` over the raw strings with `PPG_VALIDATION_KEY`; MD5 `HASH` with
   `PPG_SECRET_KEY` (or `MD5("1")` when `TEST_MODE=1`). Any failure → `400`, logged with
   the order id, PostHog exception. PPG retries a non-200 three times, which is what we
   want for a genuine key rotation window.
2. **Test-mode gate**: `TEST_MODE=1` events are processed only when `PPG_ACCEPT_TEST_IPN`
   is true (previews, staging); otherwise stored and acknowledged with `200` so PPG does not
   retry a test we do not want.
3. **Persist** a `BillingEvent` with a uniqueness key `(order_id, ipn_type_id,
   body_sha256)` where `body_sha256` excludes `IS_RESENT`. A duplicate returns `200`
   without reprocessing — PPG resends from the control panel and on its own retry schedule.
4. **Apply** inside the same transaction: resolve the organisation
   (`x-org_id` in `ORDER_CUSTOM_FIELDS` → `CheckoutIntent.nonce` → `SUBSCRIPTION_ID`
   already on a row → `CUSTOMER_EMAIL` ↔ owner membership, in that order; unresolvable →
   stored with `error`, acknowledged `200`, alert), then run the state machine
   (`billing/ipn.py::apply`). Processing is pure Python over the parsed event; mail and
   PostHog are enqueued after commit (`transaction.on_commit`).
5. **Respond `200`** only after commit. Our own exceptions → `500` so PPG retries and
   emails us.

Dates: `SUBSCRIPTION_NEXT_CHARGE_DATE` is stored both raw and parsed (`dateutil`-style
lenient ISO parsing; the exact IPN format is confirmed with the simulator in task 1 and
pinned in the fixtures).

### D5. The subscription state machine

`Subscription.status` ∈ `active | past_due | suspended | terminated | finished |
refunded | charged_back`. Transitions keyed on `IPN_TYPE_ID`:

| Event | Effect |
|---|---|
| 1 OrderCharged (new `SUBSCRIPTION_ID`) | create/replace current subscription: plan from `PRODUCT_ID`, `active`, `current_period_end=NEXT_CHARGE_DATE`, store initial order id, customer id/email; `plan_activated` |
| 13 TrialCharge | as above with `current_period_end=TRIAL_PERIOD_TILL` (not sold today; handled so a product misconfiguration cannot lock anyone out) |
| 6 SubscriptionChargeSucceed | `active`, extend period end, `failed_attempts=0`, last order id |
| 7 SubscriptionChargeFailed | `past_due`, `failed_attempts`; `plan_payment_failed` (once per cycle) |
| 8 SubscriptionSuspended | `suspended`, keep period end; reason fields |
| 9 SubscriptionRenewed | `active` (period end from payload if in the future, else unchanged until the 6 that follows) |
| 10 SubscriptionTerminated | `terminated`, keep period end; `plan_cancelled` |
| 11 SubscriptionFinished | `finished`, `current_period_end=now` |
| 2 OrderRefunded | `refunded`, `current_period_end=now` |
| 3 OrderChargedBack | `charged_back`, `current_period_end=now`, `Organization` flagged for review |
| 14 OrderChargedBackWon | recorded; no automatic restore (admin action) |
| 4, 5, 15, 17, 21, others | recorded only (15 updates `customer_email`) |

A second `OrderCharged` for an organisation that already has a current subscription
(e.g. the owner bought yearly while monthly runs) replaces the current row and keeps the
old one with `superseded_at`; the admin sees both. We do not try to cancel the old PPG
subscription automatically in v1 (no API) — the billing page shows a warning with the
PPG customer-account link.

### D6. Checkout link construction and the return page

`POST /org/<slug>/billing/checkout/` (owner only, CSRF-protected) with `period`
(`monthly|yearly`) creates `CheckoutIntent(nonce, org, user, plan_code)` and redirects to
`https://store.payproglobal.com/checkout?products[1][id]=<PPG_PRODUCTS[code]>&billing-email=…
&billing-first-name=…&language=<LANGUAGE_CODE>&x-org_id=<id>&x-user_id=<id>&x-plan=<code>
&x-nonce=<uuid>&ipn-domain=<RENDER_EXTERNAL_HOSTNAME>` (+ `use-test-mode=true&secret-key=`
when `PPG_TEST_MODE`). The nonce is the second resolution key for the webhook and the
join key for `plan_checkout_started` → `plan_activated` in PostHog.

The PPG template's thank-you redirect (control-panel setting, scenario *Fulfilled*) points
at `https://<prod host>/billing/return/`. It arrives as POST with the order parameters;
we read `ORDER_CUSTOM_FIELDS`/`x-nonce` to find the intent, render "Activating your Pro
plan…" and poll `GET /billing/return/status/?nonce=` (JSON `{state}`) every 2 s for up to
60 s, then fall back to "it can take a few minutes — we will email you". **The return
page never writes entitlements**, even though the redirect carries `HASH`/`SIGNATURE`;
one grant path means one place to audit. For previews the redirect lands on production's
return page (a single template setting) — acceptable: the page only polls, and a preview
tester follows the link back manually.

**Products and payment methods (decided 2026-10-10).** Prices 49/month, 490/year, fixed in
the panel as local prices for EUR and USD (other currencies converted by PPG). Card (corporate
or personal) and PayPal are the primary path on both products. **Pro Yearly** additionally has
"Allow users to pay with all payment methods" so a municipality can pay by wire transfer or
purchase order; PPG then turns that subscription into *manual renewal* — one invoice-by-email per
year — and the yearly checkout link carries `use-company-purchase=true` so the invoice names the
organisation and its tax number. Next to "Upgrade yearly" the owner gets **"Get a quote"**: the
same checkout URL with `display-quote=true&quote-mode=editable`, which produces a PDF quote that
can go through procurement and be paid from the link inside it. Monthly stays card/PayPal only.

The PPG template's **"Waiting for payment"** redirect scenario points at
`/billing/return/?pending=1`: the page says Pro will be activated when the transfer arrives
(typically 2–5 business days) and stops polling after the first `pending` answer. Access is still
granted only by `OrderCharged`. `OrderOnWaiting` (extended webhooks, requested from PPG) is
recorded when available so the billing page can show "awaiting bank transfer".

Rejected: iframe/pop-up checkout (needs an extra PPG parameter and parent-page redirect
handling; no UX gain for a yearly B2B purchase).

### D7. Subscription management with and without the API

`/org/<slug>/billing/` (owner and admin see it; only owner acts):

- Always: plan, state, period end, renewal type (`Auto` → "renews automatically on <date>";
  `Manual` → "renews by invoice — PayPro emails a payment link before <date>"; no "payment
  failed" dunning copy for manual), last invoice link (`INVOICE_LINK` from
  the last charged event), "Update payment method" → `…/checkout?subscr-id=<id>`
  (PPG's renewal checkout fixes a failed rebill and swaps the card), "Manage in PayPro
  customer account" → `https://cc.payproglobal.com/Customer/Account/Login`, and the
  cancellation / refund note (final copy, decided 2026-10-10):

  > **Cancelling and refunds.** You can cancel at any time. Your organisation keeps Pro
  > until the end of the period you have already paid for, then returns to the Free plan —
  > every survey, response and setting stays exactly where it is; only the Pro extras switch
  > off. Payments, invoices and refunds are handled by PayPro Global, our Merchant of
  > Record. If a payment is refunded, the organisation returns to Free immediately.
- When `PPG_API_SECRET_KEY` is set (`billing.ppg.is_configured()`): **Cancel** →
  `Subscriptions/Suspend(cancellationReasonId, sendCustomerNotification=true)`;
  **Resubscribe** (state suspended) → `Subscriptions/Renew`; **Switch to yearly/monthly**
  → `Subscriptions/ChangeProduct` (takes effect at the next charge; the page says so);
  **Email me a login link** → `Customers/SendOnetimeLoginEmail`. Each action is a POST
  with confirmation, runs synchronously (PPG answers in-line), shows the API's `errors[]`
  on failure, and **does not change our state** — the webhook that follows does. The page
  marks the row `pending_change` for 10 minutes so the owner sees "Cancellation requested…".
- `billing/ppg.py` is the project copy of the skill's client (stdlib `urllib`, `isSuccess`
  → exception, secret stripped from the echoed request before logging).

### D8. Branding gate

`_made_with_mapsurvey.html` gains one condition evaluated by the including templates'
context processor-free path: the three callers pass the survey; the partial calls
`{% has_feature survey.organization 'unbranded' as unbranded %}` and renders unless
`unbranded and not survey.show_branding`. The editor's thanks-page preview mirrors the
same rule so what the creator sees equals what respondents see. The settings UI for
`show_branding` is exposed only to organisations with the feature; others see the switch
disabled with an "Upgrade to Pro" hint. Public results `/r/<slug>/` uses the same partial
(spec requires the badge there too).

### D9. Pro help channel

`/org/<slug>/help/` behind `@require_feature('pro_help')`: a form (kind ∈ consulting /
analysis / report / other, survey (optional FK), message, preferred contact) →
`ProHelpRequest` row → Celery task mails `CONTACT_EMAIL` with a link to the admin row
and confirms to the requester → `pro_help_requested`. Members below owner may submit
(the service is for the team, the payment is the owner's business). Free organisations
see the page with the service description and an Upgrade button, not the form. Rejected:
mailto link only — unrecorded, unmeasurable, and loses the survey context.

### D10. Settings, secrets, environments

| Setting | Prod | Preview |
|---|---|---|
| `PPG_VENDOR_ACCOUNT_ID`, `PPG_SECRET_KEY`, `PPG_VALIDATION_KEY` | dashboard secrets | inherited (`previewEnvRenderServiceName: mapsurvey`) |
| `PPG_API_SECRET_KEY` | unset until issued | unset |
| `PPG_PRODUCTS` | JSON `{"pro_monthly": id, "pro_yearly": id}` | same ids |
| `PPG_ACCEPT_TEST_IPN` | `false` | `true` |
| `PPG_TEST_MODE` | `false` | `true` (links carry test params) |
| `PPG_IPN_ALLOWED_IPS` | default list from docs | same |

Webhook routing: PPG `Integration → IPN URLs` gets `https://mapsurvey.org/billing/ipn/`
and `https://*.onrender.com/billing/ipn/`; every link carries `ipn-domain`. Task 1
verifies the wildcard matches `mapsurvey-pr-<n>.onrender.com`; if not, previews set
`PPG_IPN_DOMAIN` to a registered staging hostname and the IPN simulator is used instead.

`manage.py ppg_check` calls `Products/GetStoreProducts` for the configured ids (needs the
API) or, without the API, prints the checkout URLs to open by hand.

## Risks / Trade-offs

- [Webhook never arrives (misconfigured IPN URL, PPG outage)] → return page explains the
  delay; `Reports → Others → IPN` resend; nightly `ppg_reconcile` once the API exists;
  until then an admin action "attach subscription by order id" that pulls nothing from
  PPG but lets us record a manually verified order.
- [Signature key rotated in the panel without a deploy] → all events 400, PPG retries 3×
  and emails us; alert on the first 400; settings read at request time so a dashboard
  change + restart fixes it.
- [`ORDER_CUSTOM_FIELDS` encoding differs from the documented example] → resolution falls
  through nonce → subscription id → owner email; fixtures captured from the real simulator
  in task 1 pin the format.
- [Wildcard IPN URL does not match Render preview hosts] → previews test with the IPN
  simulator pointed at the preview URL (works regardless of routing) and `ipn-domain` is
  revisited; production is unaffected.
- [Owner buys twice (monthly, then yearly)] → second row supersedes, warning on the page,
  manual cleanup via PPG panel; proper API-driven switch is the "Switch period" action.
- [Test events accepted on production by mistake] → gated by `PPG_ACCEPT_TEST_IPN=false`;
  test rows are still stored and visible in admin.
- [Chargeback-won restores access automatically and we lose money again] → no automatic
  restore; admin decides.
- [API actions change PPG state but the webhook is late] → `pending_change` marker and
  honest copy; our entitlement never leads PPG, it follows.
- [Unauthenticated endpoint as a DoS surface] → IP allow-list check first (no DB), 400 on
  everything else, no logging of bodies before verification beyond order id.

## Migration Plan

1. Deploy with the app installed, endpoint live, `PPG_ACCEPT_TEST_IPN=false`, no products
   configured → nothing changes for users; badge still renders for everyone.
2. Control panel: create the two products (49/490, local prices EUR+USD, IPN URL, yearly:
   "Allow users to pay with all payment methods"; monthly: card + PayPal only),
   copy secret/validation keys into Render, set thank-you redirect, add IPN URLs; email PPG
   for the API key and IP whitelist.
3. Preview: place test orders (test cards), watch `BillingEvent` fill; run the simulator for
   every event type; capture fixtures.
4. Production: set `PPG_PRODUCTS`, show the Upgrade button (feature flag
   `PPG_PRODUCTS` non-empty is the switch). First real order is ours.
5. Rollback: unset `PPG_PRODUCTS` → Upgrade button and Pro pages hide; existing
   entitlements keep working from stored rows; the endpoint keeps acknowledging.

## Open Questions

- Exact IPN date format and multi-field `ORDER_CUSTOM_FIELDS` encoding — resolved in task 1
  with the simulator.
- Whether admins (not only owners) may start checkout — v1: owner only, mirroring
  `org_settings`.
