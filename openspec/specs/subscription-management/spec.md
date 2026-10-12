# subscription-management Specification

## Purpose
TBD - created by archiving change paywall-payproglobal. Update Purpose after archive.
## Requirements
### Requirement: Owners and admins can see the billing page; only owners act
`/org/<slug>/billing/` SHALL be visible to members with role `owner` or `admin` and SHALL return
HTTP 403 to other members and outsiders. Every action on the page SHALL be a POST accepted only
from `owner`.

#### Scenario: Admin views
- **WHEN** an admin opens the billing page
- **THEN** the page renders with status information and without action buttons

#### Scenario: Editor is refused
- **WHEN** an editor opens the billing page
- **THEN** the response is HTTP 403

### Requirement: The page states the plan, its state and what happens next
The page SHALL show the current plan, a human state (Free / Active / Payment failed /
Cancelling until <date> / Ended), the period end, the renewal type, the PayPro subscription id,
the last invoice link when known, and the "Cancelling and refunds" note stating that cancelling
keeps Pro until the end of the paid period and then returns the organisation to Free with all
data intact, that payments, invoices and refunds are handled by PayPro Global as Merchant of
Record, and that a refund returns the organisation to Free immediately.

#### Scenario: Active subscription
- **WHEN** the organisation is Pro with `status=active`
- **THEN** the page shows "Pro", the next charge date and the invoice link of the last charged order

#### Scenario: Manual renewal
- **WHEN** the subscription's renewal type is `Manual`
- **THEN** the page says the plan renews by invoice and that PayPro emails a payment link before the period end, and shows no "payment failed" dunning copy

#### Scenario: Awaiting bank transfer
- **WHEN** the latest stored event for the organisation's pending order is `OrderOnWaiting`
- **THEN** the page shows "awaiting bank transfer" for that order while the current entitlement is unchanged

#### Scenario: Past due
- **WHEN** `status=past_due`
- **THEN** the page shows "Payment failed", the number of attempts, and an "Update payment method" button

### Requirement: Payment recovery works without the API
The page SHALL always offer "Update payment method" linking to
`https://store.payproglobal.com/checkout?subscr-id=<ppg_subscription_id>` and "Manage in
PayPro customer account" linking to `https://cc.payproglobal.com/Customer/Account/Login`.

#### Scenario: Links present
- **WHEN** any subscription exists for the organisation
- **THEN** both links are rendered with the stored subscription id

### Requirement: API-backed actions appear only when the API is configured
When `PPG_API_SECRET_KEY` is set, the page SHALL offer **Cancel** (calls
`Subscriptions/Suspend` with the owner's chosen reason and `sendCustomerNotification=true`),
**Resubscribe** when `status=suspended` (calls `Subscriptions/Renew`), **Switch to yearly /
monthly** (calls `Subscriptions/ChangeProduct` with the other configured product id) and
**Email me a login link** (calls `Customers/SendOnetimeLoginEmail`). When the key is absent these
controls SHALL NOT be rendered and their endpoints SHALL return HTTP 404.

#### Scenario: Without API key
- **WHEN** `PPG_API_SECRET_KEY` is empty
- **THEN** the page shows no Cancel / Resubscribe / Switch buttons and `POST /org/<slug>/billing/cancel/` returns HTTP 404

#### Scenario: Cancel with API
- **WHEN** an owner confirms Cancel with reason "I no longer need this product"
- **THEN** `Subscriptions/Suspend` is called with `cancellationReasonId=2`, the page shows "Cancellation requested — Pro stays active until <period end>" and the local status is unchanged until the `SubscriptionSuspended` webhook arrives

#### Scenario: API error surfaced
- **WHEN** the API answers `isSuccess=false` with `errors`
- **THEN** the page shows the error messages and nothing is marked pending

### Requirement: Actions never lead the webhook
No action on the billing page SHALL change `Subscription.status` or `current_period_end`
directly; it MAY set a `pending_change` marker that expires after 10 minutes and is cleared by
the next applied webhook.

#### Scenario: Pending marker clears
- **WHEN** Cancel was requested and `SubscriptionSuspended` is applied
- **THEN** `pending_change` is cleared and the page shows "Cancelling until <date>"

### Requirement: Duplicate subscriptions are visible
The page SHALL show a warning naming both subscription ids and pointing to the PayPro customer
account to cancel the unwanted one whenever more than one non-superseded PayPro subscription maps
to the organisation, or a superseded one is still `active` by its last event.

#### Scenario: Two purchases
- **WHEN** an organisation has a superseded monthly subscription still `active` and a current yearly one
- **THEN** the warning lists both ids

