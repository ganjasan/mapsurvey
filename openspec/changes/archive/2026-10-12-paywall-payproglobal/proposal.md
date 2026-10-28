## Why

Mapsurvey has no way to take money. The product is free, the `/services/` page sells
done-with-you help by hand, and `/pro/` has been collecting what people would pay for.
The answer we are acting on is that the first paid thing is **access to us**: a Pro
organisation gets Artem personally — project consulting, analytics, reports — plus a
clean, unbranded product. That is a service sold on a subscription, and it needs a
payment rail, a verified "this organisation is Pro" fact, and a place where Pro
customers can ask for the help they paid for.

PayPro Global is the rail: it is a Merchant of Record, so tax, invoices, chargebacks
and card storage stay on their side. Our side is a checkout link out, webhooks in,
and an entitlement derived from them. Building that entitlement layer generically now
— not as a branding flag — is what lets the feature set that will follow later land
as one registry entry each instead of a second billing project.

## What Changes

- **New `billing` app** with `Plan`, `Subscription` (one current per organisation),
  `BillingEvent` (append-only raw webhook log) and `CheckoutIntent`.
- **Upgrade flow**: "Upgrade to Pro" on the organisation settings page (owner only)
  → `POST /org/<slug>/billing/checkout/` records a `CheckoutIntent` and redirects to
  the PayPro hosted checkout with our identifiers in `x-*` parameters, the buyer's
  email prefilled and `ipn-domain` so preview environments receive their own
  webhooks. A return page `/billing/return/` polls activation state; it never grants.
- **Webhook endpoint** `POST /billing/ipn/`: verifies source IP, SHA256 `SIGNATURE`
  and MD5 `HASH`, persists the raw event idempotently, then applies it to the
  organisation's subscription. Handles `OrderCharged`, `SubscriptionChargeSucceed`,
  `SubscriptionChargeFailed`, `SubscriptionSuspended`, `SubscriptionRenewed`,
  `SubscriptionTerminated`, `SubscriptionFinished`, `OrderRefunded`,
  `OrderChargedBack`; logs and acknowledges everything else. Test-mode events are
  accepted only where a setting allows it.
- **Entitlements**: `billing.entitlements(organization)` is the single source of
  "what this organisation may do"; a feature registry (`FEATURES`) lists Pro
  capabilities; a view decorator and a template tag gate on them;
  `survey/ai/quota.py::check_quota` reads the same source (still permissive for
  every plan in this change). Access follows the PayPro rule: Pro until the current
  period end, including after a suspension or termination; cut immediately on
  refund, chargeback or finish.
- **Two features gated in this change**: `unbranded` (the "Made with Mapsurvey"
  badge finally honours `show_branding`, but only for Pro organisations) and
  `pro_help` (a request form for consulting / analysis / a report, visible to Pro
  organisations, delivered to us by email and recorded).
- **Subscription management page** `/org/<slug>/billing/`: plan, status, next
  charge date, last invoice link, "Update payment method" (PayPro renewal checkout
  `?subscr-id=`), "Manage in PayPro customer account". Cancel, resubscribe and
  monthly↔yearly switch call the PayPro API and are shown only when the API is
  configured (`PPG_API_SECRET_KEY` present) — the key and IP whitelist do not exist
  yet.
- **Operations**: settings for keys and product IDs, Django admin for events and
  subscriptions, PostHog events (`plan_checkout_started`, `plan_activated`,
  `plan_payment_failed`, `plan_cancelled`, `plan_lapsed`, `pro_help_requested`), a
  management command that checks the configured product IDs against PayPro, and a
  checklist of control-panel steps (products, IPN URL, keys, thank-you redirect,
  the email requesting API access).

Nothing free today becomes paid. No new Pro feature beyond the two above.

## Capabilities

### New Capabilities

- `billing-checkout`: starting a purchase — who may upgrade, what the checkout link
  carries, how the return page behaves, test mode.
- `billing-webhooks`: receiving PayPro IPN events — verification, idempotent
  persistence, acknowledgement rules, which events change what.
- `plan-entitlements`: the organisation-level entitlement model — plans, period
  end, the access rule across statuses, the feature registry and gate helpers,
  what `check_quota` sees.
- `subscription-management`: the organisation's billing page and the self-service
  actions available with and without API access.
- `pro-help-channel`: the Pro request form — who sees it, what it collects, where
  it goes, what is recorded.

### Modified Capabilities

- `made-with-badge`: the badge SHALL render on every respondent-facing surface
  **unless** the survey's organisation holds the `unbranded` entitlement and the
  survey has `show_branding` off. Today it renders unconditionally.

## Impact

- New app `billing/` (models, migration, views, urls, admin, `entitlements.py`,
  `ipn.py`, `ppg.py` client, `features.py`, templates, tests). Registered in
  `INSTALLED_APPS`; URLs mounted from `mapsurvey/urls.py`.
- `survey/org_views.py` + `templates/org/org_settings.html`: Upgrade / Billing
  entry points. `templates/partials/_made_with_mapsurvey.html` and its three
  callers: gate on entitlement. `survey/ai/quota.py`: reads entitlements.
- `mapsurvey/settings.py`: `PPG_VENDOR_ACCOUNT_ID`, `PPG_SECRET_KEY`,
  `PPG_VALIDATION_KEY`, `PPG_API_SECRET_KEY` (optional), `PPG_PRODUCTS`
  (`{"pro_monthly": id, "pro_yearly": id}`), `PPG_ACCEPT_TEST_IPN`,
  `PPG_TEST_MODE`, `PPG_IPN_ALLOWED_IPS`. `render.yaml`: the new env vars
  (secrets unset), preview group inherits `PPG_ACCEPT_TEST_IPN=true`.
- Outbound dependency on PayPro: webhooks must reach `/billing/ipn/` on
  production and on previews (wildcard IPN URL + `ipn-domain`); API calls need the
  key and Render's outbound IPs whitelisted — until then the page degrades to
  links into the PayPro customer account.
- Email: one new outbound message (Pro help request) via the existing mail
  backend. PostHog: six new events, all keyed on the acting user.
- Legal/UX copy: billing page states that payment, invoices and refunds are
  handled by PayPro Global as Merchant of Record.
