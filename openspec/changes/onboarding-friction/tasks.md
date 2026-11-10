## 1. Navigation Pro mark

- [x] 1.1 `pro_nav_mark` inclusion tag in `billing/templatetags/billing_tags.py` over `pro_badge_state`; template `billing/_pro_nav_mark.html` (lock only when `locked`)
- [x] 1.2 Lock style in `css/pro_badge.css`
- [x] 1.3 `_app_sidebar.html`: modules, Integrations and Library use `pro_nav_mark`; drop the now-unused `.app-item-mark .pro-badge__extra` rule in `app_sidebar.css`
- [x] 1.4 Tests: tag states (`billing/tests/test_plan_entitlements.py`), sidebar shows no Pro label on Pro / trial / startable and a lock when locked (`survey/tests/test_workspace_navigation.py`)

## 2. Confirm-email banner

- [x] 2.1 Remove the banner markup and its CSS from `editor/partials/_confirm_email_banner.html`; keep the dialog and the resend script; update the partial's comment
- [x] 2.2 Tests in `survey/tests/test_sign_in_grace_period.py`: no banner on the dashboard and the editor; the dialog is present for an unconfirmed creator and absent once confirmed

## 3. Start page: two cards

- [x] 3.1 Remove the *Use your AI assistant* card and its CSS from `editor/survey_start.html`; two-column grid, narrower page
- [x] 3.2 Test in `survey/tests/test_survey_start_chooser.py`: two cards, no agent card or link inside the cards
- [x] 3.3 Help centre pages that describe the third card

## 4. Onboarding rail

- [x] 4.1 `app_nav.onboarding` in `survey/context_processors.py` (no canonical, non-trashed survey in the active workspace; owner/admin/editor)
- [x] 4.2 `_app_sidebar.html`: the before-paint script picks the rail during onboarding unless `msSidebar` is `wide`; `data-onboarding="1"` on the sidebar
- [x] 4.3 Tests in `survey/tests/test_workspace_navigation.py`: start page + dashboard marked; not after the first survey; never for viewers

## 5. Chat bubble on the editor

- [x] 5.1 `_support_chat.html` editor-bubble mode: shown on desktop, hidden below 768 px, "×" hides and remembers, `showSupportBubble` restores; never an unread pop-up on the editor
- [x] 5.2 "Show chat button" in `_help_menu.html`; both creator bases include the partial with `editor_bubble=True`
- [x] 5.3 New msgids in the offered catalogs + ru, compiled
- [x] 5.4 Tests in `survey/tests/test_support_chat.py`

## 6. Wrap-up

- [x] 6.1 CLAUDE.md: grace period, Pro marks, ways to start, support chat
- [ ] 6.2 Touched test modules green; check the sidebar, the start page and the bubble in the browser
