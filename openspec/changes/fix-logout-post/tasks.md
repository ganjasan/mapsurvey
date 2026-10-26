## 1. Code

- [x] 1.1 `partials/_logout_form.html`: POST form with `{% csrf_token %}`, link-styled button, class from `btn_class`
- [x] 1.2 Replace the Logout anchors in `editor/editor_base.html` (account menu, desktop header), `base.html`, `base_landing.html` with the partial

## 2. Tests

- [x] 2.1 `LogoutTest`: POST logs out and redirects to `/`; GET leaves the session signed in
- [x] 2.2 `LogoutTest`: dashboard, editor page and a landing page render the POST form and no GET logout link

## 3. Verify

- [x] 3.1 Browser check: Logout from the editor account menu and from the landing nav signs out
