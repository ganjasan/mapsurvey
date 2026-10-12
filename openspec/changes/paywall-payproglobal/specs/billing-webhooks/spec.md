# billing-webhooks Specification

## Purpose
Receiving PayPro Global IPN webhooks at `/billing/ipn/`: verification, idempotent persistence,
acknowledgement rules, and which events change the organisation's subscription.

## ADDED Requirements

### Requirement: Every webhook is verified before anything is stored or applied
The endpoint SHALL accept only `POST`, SHALL require the client IP (`request.cf_ip`) to be in
`PPG_IPN_ALLOWED_IPS`, SHALL verify `SIGNATURE` as
`SHA256(ORDER_ID + ORDER_STATUS + ORDER_TOTAL_AMOUNT + CUSTOMER_EMAIL + PPG_VALIDATION_KEY + TEST_MODE + IPN_TYPE_NAME)`
over the raw received strings, and SHALL verify `HASH` as `MD5(ORDER_ID + PPG_SECRET_KEY)`
(`MD5("1")` when `TEST_MODE=1`). Any failed check SHALL answer HTTP 400 and record nothing but a
log line with the order id.

#### Scenario: Valid event
- **WHEN** a POST arrives from `198.199.123.239` with a correct SIGNATURE and HASH
- **THEN** the event is persisted and the response is HTTP 200

#### Scenario: Wrong signature
- **WHEN** a POST arrives from an allowed IP with a SIGNATURE that does not match
- **THEN** the response is HTTP 400 and no `BillingEvent` is created

#### Scenario: Unknown source IP
- **WHEN** a POST arrives from an IP not in the allow-list, even with valid signatures
- **THEN** the response is HTTP 400

#### Scenario: Test order hash
- **WHEN** a POST has `TEST_MODE=1` and `HASH=c4ca4238a0b923820dcc509a6f75849b`
- **THEN** the HASH check passes

### Requirement: Events are persisted raw and exactly once
Each verified event SHALL be stored as a `BillingEvent` with the full payload, `ipn_type_id`,
`order_id`, `subscription_id`, `test_mode`, `is_resent`, the verification methods that passed and
a `body_sha256` computed over the payload without `IS_RESENT`. A second event with the same
`(order_id, ipn_type_id, body_sha256)` SHALL be acknowledged with HTTP 200 and SHALL NOT be
applied again.

#### Scenario: PayPro resends an event
- **WHEN** the same `SubscriptionChargeSucceed` arrives twice, the second with `IS_RESENT=1`
- **THEN** one `BillingEvent` exists, the subscription's period end was extended once, and both responses were HTTP 200

### Requirement: Test-mode events are applied only where allowed
When `TEST_MODE=1` and `PPG_ACCEPT_TEST_IPN` is false the event SHALL be stored, marked
`ignored_test`, and acknowledged with HTTP 200 without touching any subscription.

#### Scenario: Test event on production
- **WHEN** a test-mode `OrderCharged` arrives with `PPG_ACCEPT_TEST_IPN=false`
- **THEN** a `BillingEvent` exists with `ignored_test=true`, no subscription changes, response HTTP 200

#### Scenario: Test event on a preview
- **WHEN** the same event arrives with `PPG_ACCEPT_TEST_IPN=true`
- **THEN** the subscription is created as for a real order

### Requirement: The organisation is resolved from our own identifiers first
The handler SHALL resolve the organisation by, in order: `x-org_id` in `ORDER_CUSTOM_FIELDS`;
the `CheckoutIntent` matching `x-nonce`; an existing `Subscription` with the event's
`SUBSCRIPTION_ID`; the owner membership whose user email equals `CUSTOMER_EMAIL`. If none matches
the event SHALL be stored with `error="unresolved"`, acknowledged with HTTP 200, and reported to
error tracking.

#### Scenario: Rebill without custom fields
- **WHEN** a `SubscriptionChargeSucceed` arrives whose `ORDER_CUSTOM_FIELDS` is empty but whose `SUBSCRIPTION_ID` matches a stored subscription
- **THEN** that subscription is updated

#### Scenario: Unresolvable event
- **WHEN** an event matches no organisation by any key
- **THEN** it is stored with `error="unresolved"` and the response is HTTP 200

### Requirement: Subscription events drive the state machine
The handler SHALL apply events to the organisation's current `Subscription` as follows:
`OrderCharged` with a new `SUBSCRIPTION_ID` creates an `active` subscription with the plan derived
from `PRODUCT_ID` via `PPG_PRODUCTS` and `current_period_end = SUBSCRIPTION_NEXT_CHARGE_DATE`;
`TrialCharge` does the same with `TRIAL_PERIOD_TILL`; `SubscriptionChargeSucceed` sets `active`
and extends the period end; `SubscriptionChargeFailed` sets `past_due` and records the attempt
count; `SubscriptionSuspended` sets `suspended`; `SubscriptionRenewed` sets `active`;
`SubscriptionTerminated` sets `terminated`; `SubscriptionFinished` sets `finished` and ends the
period now; `OrderRefunded` sets `refunded` and ends the period now; `OrderChargedBack` sets
`charged_back`, ends the period now and flags the organisation for review. Cancellation reason
and `ACTION_REASON` SHALL be stored when present. All other event types SHALL be stored without
state change, except `OrderCustomerInformationChanged`, which updates `customer_email`.

#### Scenario: Initial purchase
- **WHEN** `OrderCharged` arrives with `SUBSCRIPTION_ID=954874`, `PRODUCT_ID=<pro_yearly>`, `SUBSCRIPTION_NEXT_CHARGE_DATE` one year ahead, `x-org_id=42`
- **THEN** organisation 42 has a current subscription `plan=pro`, `status=active`, `ppg_subscription_id=954874`, `current_period_end` equal to that date

#### Scenario: Failed rebill then suspension
- **WHEN** `SubscriptionChargeFailed` (attempt 3) and `SubscriptionSuspended` arrive for an active subscription
- **THEN** status is `suspended`, `failed_attempts=3`, and `current_period_end` is unchanged

#### Scenario: Refund
- **WHEN** `OrderRefunded` arrives for the subscription's last order
- **THEN** status is `refunded` and `current_period_end` is not later than now

#### Scenario: Replacement purchase
- **WHEN** `OrderCharged` arrives with a new `SUBSCRIPTION_ID` for an organisation that already has a current subscription
- **THEN** the old row gets `superseded_at` set, the new row becomes current, and the billing page shows a duplicate-subscription warning

### Requirement: Failures of our own code make PayPro retry
If applying a verified, non-duplicate event raises, the transaction SHALL roll back (no
`BillingEvent` kept) and the response SHALL be HTTP 500, so PayPro retries and notifies us.

#### Scenario: Database error during apply
- **WHEN** applying an event raises an exception
- **THEN** no `BillingEvent` row remains and the response status is 500

### Requirement: Transitions are measured
Applying events SHALL emit PostHog events keyed on the buyer when known: `plan_activated` on
the first `OrderCharged`/`TrialCharge`, `plan_payment_failed` on the first failed attempt of a
cycle, `plan_cancelled` on `SubscriptionSuspended` or `SubscriptionTerminated` initiated by the
customer or vendor. Emission SHALL happen after the transaction commits and SHALL never fail the
request.

#### Scenario: Activation emitted once
- **WHEN** `OrderCharged` is applied and later resent
- **THEN** `plan_activated` is emitted exactly once
