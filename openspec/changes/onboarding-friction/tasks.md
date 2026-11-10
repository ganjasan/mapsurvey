## 1. Navigation Pro mark

- [x] 1.1 `pro_nav_mark` inclusion tag in `billing/templatetags/billing_tags.py` over `pro_badge_state`; template `billing/_pro_nav_mark.html` (lock only when `locked`)
- [x] 1.2 Lock style in `css/pro_badge.css`
- [x] 1.3 `_app_sidebar.html`: modules, Integrations and Library use `pro_nav_mark`; drop the now-unused `.app-item-mark .pro-badge__extra` rule in `app_sidebar.css`
- [x] 1.4 Tests: tag states (`billing/tests/test_plan_entitlements.py`), sidebar shows no Pro label on Pro / trial / startable and a lock when locked (`survey/tests/test_workspace_navigation.py`)

## 2. Confirm-email banner

- [x] 2.1 Remove the banner markup and its CSS from `editor/partials/_confirm_email_banner.html`; keep the dialog and the resend script; update the partial's comment
- [x] 2.2 Tests in `survey/tests/test_sign_in_grace_period.py`: no banner on the dashboard and the editor; the dialog is present for an unconfirmed creator and absent once confirmed

## 3. Wrap-up

- [x] 3.1 CLAUDE.md: the grace-period paragraph no longer names a banner; the Pro trial paragraph names `pro_nav_mark` for navigation
- [ ] 3.2 Run the touched test modules (done: 815 tests OK); check the sidebar and the dashboard in the browser
