# billing-checkout Specification

## Purpose
Starting a Pro purchase: who may upgrade, what the PayPro Global checkout link carries, how the
return page behaves, and how test mode is confined to environments that allow it.

## ADDED Requirements

### Requirement: Only an organisation owner can start checkout
The system SHALL expose "Upgrade to Pro" on the organisation settings and billing pages only to
members with the `owner` role, and SHALL reject checkout requests from any other user with HTTP 403.

#### Scenario: Owner starts checkout
- **WHEN** an owner submits the checkout form with period `yearly`
- **THEN** a `CheckoutIntent` is recorded and the response is a redirect to `https://store.payproglobal.com/checkout`

#### Scenario: Admin cannot start checkout
- **WHEN** a member with role `admin` submits the checkout form
- **THEN** the response is HTTP 403 and no `CheckoutIntent` is recorded

### Requirement: The checkout link identifies the organisation, the buyer and the intent
The checkout URL SHALL contain `products[1][id]` set to the PayPro product id configured for the
chosen period, `x-org_id`, `x-user_id`, `x-plan` and `x-nonce` (the intent's UUID), the buyer's
email in `billing-email`, the UI language in `language`, and `ipn-domain` set to the current
host so webhooks route to the originating environment.

#### Scenario: Link contents
- **WHEN** owner 7 of organisation 42 starts checkout for `pro_monthly` on host `mapsurvey-pr-12.onrender.com`
- **THEN** the redirect URL contains `products[1][id]=<PPG_PRODUCTS.pro_monthly>`, `x-org_id=42`, `x-user_id=7`, `x-plan=pro_monthly`, `x-nonce=<intent uuid>`, `billing-email=<owner email>` and `ipn-domain=mapsurvey-pr-12.onrender.com`

#### Scenario: Custom values never contain separators
- **WHEN** any `x-` value would contain `,` or `=`
- **THEN** the checkout is refused with a server error logged, because `ORDER_CUSTOM_FIELDS` could not be parsed back

### Requirement: The yearly product supports organisation purchase and quotes
The yearly checkout URL SHALL additionally carry `use-company-purchase=true`, and the owner SHALL
be offered a "Get a quote" action that redirects to the same yearly checkout URL with
`display-quote=true&quote-mode=editable`. The monthly URL SHALL carry neither.

#### Scenario: Yearly upgrade
- **WHEN** an owner starts checkout for `pro_yearly`
- **THEN** the redirect URL contains `use-company-purchase=true` and no `display-quote`

#### Scenario: Quote
- **WHEN** an owner clicks "Get a quote"
- **THEN** a `CheckoutIntent` is recorded and the redirect URL contains `products[1][id]=<pro_yearly>`, `display-quote=true` and `quote-mode=editable`

#### Scenario: Monthly upgrade
- **WHEN** an owner starts checkout for `pro_monthly`
- **THEN** the redirect URL contains neither `use-company-purchase` nor `display-quote`

### Requirement: Test mode is confined by configuration
The checkout link SHALL include `use-test-mode=true&secret-key=<PPG_SECRET_KEY>` only when
`PPG_TEST_MODE` is true, and the Upgrade controls SHALL be hidden entirely when `PPG_PRODUCTS`
is empty.

#### Scenario: Preview environment
- **WHEN** `PPG_TEST_MODE=true`
- **THEN** the redirect URL contains `use-test-mode=true` and `secret-key=`

#### Scenario: Production
- **WHEN** `PPG_TEST_MODE=false`
- **THEN** the redirect URL contains neither parameter

#### Scenario: Products not configured
- **WHEN** `PPG_PRODUCTS` is empty
- **THEN** the settings and billing pages show no Upgrade control and the checkout endpoint returns HTTP 404

### Requirement: The return page reports activation without granting it
`/billing/return/` SHALL accept the PayPro thank-you redirect (GET or POST), look up the intent by
`x-nonce`, and render a page that polls `/billing/return/status/?nonce=` until the organisation's
entitlement becomes Pro or 60 seconds pass. The return page and the status endpoint SHALL NOT
create or modify any `Subscription`.

#### Scenario: Webhook already processed
- **WHEN** the return page is opened after the `OrderCharged` webhook was applied
- **THEN** the status endpoint answers `{"state": "active"}` and the page shows the plan as active with a link to the billing page

#### Scenario: Webhook still pending
- **WHEN** the return page is opened before any webhook arrived
- **THEN** the status endpoint answers `{"state": "pending"}` and the page keeps polling; after 60 s it shows "this can take a few minutes" with the billing page link

#### Scenario: Waiting for payment
- **WHEN** the return page is opened with `pending=1` (PayPro's "Waiting for payment" redirect)
- **THEN** the page states that Pro will be activated when the bank transfer arrives, typically within 2–5 business days, and does not keep polling

#### Scenario: Unknown nonce
- **WHEN** the return page is opened with a nonce that matches no intent
- **THEN** the page shows a neutral "thank you, we are processing your order" message without organisation data

### Requirement: Buyers from a preview are returned to that preview
The production return page SHALL forward the buyer with HTTP 303 to `https://<host>/billing/return/` (keeping `x-nonce` and
`pending`) when the checkout's `ipn-domain` names another host that fully matches
`PPG_RETURN_FORWARD_HOSTS` (default `mapsurvey-pr-<n>.onrender.com`), and SHALL render normally
for any other value, so it is never an open redirect. (PayPro allows one thank-you redirect URL
per page template, and it points at production.)

#### Scenario: Order placed on a preview
- **WHEN** the return page receives `ipn-domain=mapsurvey-pr-276.onrender.com`
- **THEN** the response is a 303 to `https://mapsurvey-pr-276.onrender.com/billing/return/?x-nonce=<nonce>`

#### Scenario: Foreign host
- **WHEN** `ipn-domain` is `evil.example`
- **THEN** the page renders without redirecting

### Requirement: Checkout start is measured
Starting checkout SHALL emit the PostHog event `plan_checkout_started` with `org_id`, `plan`
and `nonce`, keyed on the acting user, and SHALL never fail the request if analytics is down.

#### Scenario: Event emitted
- **WHEN** an owner starts checkout
- **THEN** `plan_checkout_started` is emitted with the intent's nonce
