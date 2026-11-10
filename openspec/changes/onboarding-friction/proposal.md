## Why

Two pieces of chrome push new creators off the onboarding flow (#638). The app sidebar hangs a
Pro mark on Sites, API, MCP and Map styles; on a Free workspace the sidebar hides the mark's
"· free to try", so a filled violet "★ PRO" reads as "paid, not for you" — while the first use of
any of them would start the free trial by itself. On a Pro workspace the same marks tell a paying
creator nothing. And every editor page and the dashboard of a new account carry a yellow
"Confirm your email address… you can sign in for N hours more" strip, which talks about a
deadline before the creator has done anything the deadline guards.

## What Changes

- Sidebar items carry no Pro mark while the feature is in the plan, in a live trial, or would
  start the trial on first use. A workspace that can no longer use it (`locked`) gets a small grey
  lock without the word "Pro". The mark comes from a new registry tag `{% pro_nav_mark org "key" %}`.
- Point-of-use marks (`{% pro_badge %}` on the badge switch, *Enter a response*, the API &
  connections page, Pro help entries) are unchanged: that is where "free to try" / "N left" is read.
- The confirm-your-email banner strip is removed from every editor page and the dashboard. The
  "Confirm your email to publish" dialog (opened on `403 email_unconfirmed`) and the resend
  script it uses stay; the publish and invitation refusals are unchanged.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `workspace-navigation`: Integrations and Library items no longer carry the Pro mark; a lock only when locked.
- `plan-entitlements`: adds the navigation variant of the Pro mark (`pro_nav_mark`).
- `sign-in-grace-period`: the editor no longer shows the confirm-email banner; the reminder lives in the publish dialog.

## Impact

- `billing/templatetags/billing_tags.py`, new `billing/templates/billing/_pro_nav_mark.html`,
  `css/pro_badge.css`.
- `survey/templates/partials/_app_sidebar.html`, `survey/assets/css/app_sidebar.css`.
- `survey/templates/editor/partials/_confirm_email_banner.html` (banner markup and its CSS go;
  dialog and script stay).
- Tests: `survey/tests/test_sign_in_grace_period.py`, `survey/tests/test_workspace_navigation.py`,
  `billing/tests/test_plan_entitlements.py`.
- No model, URL or API change. Rollback = revert.
