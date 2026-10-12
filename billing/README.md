# Billing — Pro on PayPro Global

Change `paywall-payproglobal` (issue #268). PayPro Global is the Merchant of Record: checkout,
cards, tax, invoices, refunds and chargebacks are theirs. Our side is the `billing` app: a checkout
link out, verified webhooks in, and the entitlement derived from them. Design and specs:
`openspec/changes/paywall-payproglobal/`.

## How it works (one paragraph)

The organisation owner clicks **Upgrade** → `POST /org/<slug>/billing/checkout/` records a
`CheckoutIntent` and redirects to PayPro's hosted checkout with `x-org_id`, `x-user_id`, `x-plan`,
`x-nonce` and `ipn-domain`. PayPro POSTs webhooks (IPN) to `/billing/ipn/`; the view verifies the
source IP, the SHA256 `SIGNATURE` and the MD5 `HASH`, stores the event once (`BillingEvent`), and
applies it to the organisation's `Subscription`. `billing.entitlements.for_organization(org)` turns
that row into "Pro until <date>" using PayPro's own rule (access until the paid period ends, also
after a cancellation; cut immediately on refund, chargeback or finish). Nothing else grants access.

## Settings

| Env var | Where it comes from | Prod (service `mapsurvey`) | Preview |
|---|---|---|---|
| `PPG_VENDOR_ACCOUNT_ID` | Account settings → Business info | set | env group `mapsurvey-shared` |
| `PPG_SECRET_KEY` | Store settings → General settings → Integration ("secret key") | set | env group `mapsurvey-shared` |
| `PPG_VALIDATION_KEY` | same tab ("validation key") | set | env group `mapsurvey-shared` |
| `PPG_API_SECRET_KEY` | same tab, **issued by the account manager on request** | unset until issued | unset |
| `PPG_PRODUCTS` | `{"pro_monthly": 138966, "pro_yearly": 138969}` — Store settings → Product setup | set at launch | set by hand on the preview service under test; never in the group |
| `PPG_ACCEPT_TEST_IPN` | apply `TEST_MODE=1` webhooks | `false` | `true` |
| `PPG_TEST_MODE` | add `use-test-mode=true&secret-key=…` to checkout links | `false` | `true` |
| `PPG_IPN_DOMAIN` | override the `ipn-domain` host (default `RENDER_EXTERNAL_HOSTNAME`) | unset | unset unless the wildcard does not match |
| `PPG_IPN_ALLOWED_IPS` | PayPro's published webhook IPs (default in settings.py) | default | default |

Previews get secrets only from the `mapsurvey-shared` env group (PR #201): Render never copies a
`sync: false` value into a preview.

**`PPG_PRODUCTS` empty = nothing is sold**: no Upgrade buttons, checkout endpoint 404, Pro pages show
the offer only. That is the rollback switch.

`python manage.py ppg_check` prints what is configured, the URLs to put into the control panel and —
once the API key exists — verifies the product ids against the store.

## Control panel checklist (do once, in this order)

1. **Products** — Store settings → Product setup → *Add product*, twice:
   - *Mapsurvey Pro — monthly*: charging type **Subscription plan**, 1 month, auto renewal, no
     trial, grace period default. Prices: 49 as **local currency** price for USD and EUR (other
     currencies converted). Step 5 *Checkout*: leave only Credit/Debit card and PayPal.
   - *Mapsurvey Pro — yearly*: 1 year, auto renewal, prices 490 USD / 490 EUR, and tick **Allow
     users to pay with all payment methods** (a buyer who picks wire transfer or purchase order
     becomes a *manual renewal* customer: one invoice by email per year).
   - On step 1 of both: **IPN URL** = `https://mapsurvey.org/billing/ipn/`.
   - Note both product ids → `PPG_PRODUCTS`.
2. **Keys** — Store settings → General settings → Integration: copy *secret key* and *validation
   key* into Render (`PPG_SECRET_KEY`, `PPG_VALIDATION_KEY`). Same tab, **IPN URLs** (one per
   line): `https://mapsurvey.org/billing/ipn/` and `https://*.onrender.com/billing/ipn/` so previews
   receive their own webhooks through `ipn-domain`.
3. **Thank-you redirects** — Store settings → Page templates → Edit the template used by the
   products → *1. Settings*: scenario **Fulfilled** → `https://mapsurvey.org/billing/return/`,
   scenario **Waiting for payment** → `https://mapsurvey.org/billing/return/?pending=1`, delay 0.
4. **Notifications** — Store settings → Notifications: an address for *Failed IPNs* (ours), so a
   webhook PayPro could not deliver three times reaches a human.
5. **Email to PayPro** (integration / account manager) — template below.
6. **Preview test** — open a PR titled `[render preview] …`, set the preview's `PPG_PRODUCTS`, place
   test orders with the test cards (`4532789918951515` fulfil, `4024007102303806` decline,
   `4024007159164028` full refund, `4916349044590772` chargeback, `4024007192413689` decline on the
   first rebill), and fire every event type from Developer tools → **IPN simulator** at
   `https://<preview>/billing/ipn/`. Check `BillingEvent` rows in `/admin/billing/billingevent/`
   and the organisation's billing page. Record the date format of `SUBSCRIPTION_NEXT_CHARGE_DATE`
   and the encoding of several `x-` fields in `ORDER_CUSTOM_FIELDS` in the test fixtures.
7. **Launch** — set `PPG_PRODUCTS` on production. The first real order is ours.

### Email to PayPro

> Subject: API access, IP whitelist and extended webhooks for vendor account <id>
>
> Hello — we are integrating Mapsurvey (mapsurvey.org) with PayPro Global. Please:
> 1. generate the **API secret key** for vendor account <id>;
> 2. whitelist our API source IPs: <Render outbound IPs of the `mapsurvey` web service>;
> 3. enable **extended webhooks** (`OrderOnWaiting`, `SubscriptionPaymentInfoChanged`, bank-decline
>    reasons on `OrderDeclined`) for the account;
> 4. confirm that the IPN URL rule `https://*.onrender.com/billing/ipn/` matches hosts such as
>    `mapsurvey-pr-123.onrender.com` when `ipn-domain` is passed.
>
> Thank you.

Render's outbound IPs: Dashboard → service `mapsurvey` → *Outbound IPs*. Until the key and whitelist
exist, the billing page offers "Update payment method" (`checkout?subscr-id=`) and the PayPro customer
account instead of in-app cancel/resubscribe; nothing else is affected.

## Operating it

- **Webhook log**: `/admin/billing/billingevent/` — raw payload, which checks passed, `error`
  (`unresolved`, `unknown_product`, `no_subscription`, `not_a_subscription`), `ignored_test`.
  PayPro's own log and resend: Reports → Others → IPN.
- **Subscriptions**: `/admin/billing/subscription/` — status, period end (parsed and raw), PayPro
  ids, `needs_review` after a chargeback (clear it with the admin action; access is never restored
  automatically).
- **Signature failures** return 400, are logged and reported to PostHog error tracking. Three
  failures in a row means a key changed in the panel: update the env var, restart.
- **Daily**: `reclaim.sh` (the Render cron) runs `notify_lapsed` — one `plan_lapsed` event and one
  email per owner for subscriptions whose paid period ended.
- **PostHog events**: `plan_checkout_started`, `plan_activated`, `plan_payment_failed`,
  `plan_cancelled`, `plan_lapsed`, `pro_help_requested` (`billing/events.py`), all keyed on the
  acting user.
- **Pro help requests**: `/admin/billing/prohelprequest/`; the team mail goes to `CONTACT_EMAIL`.

## Rollback

Unset `PPG_PRODUCTS` → Upgrade controls disappear and checkout 404s. Existing Pro organisations keep
their entitlement from stored rows; the webhook endpoint keeps acknowledging and recording.
