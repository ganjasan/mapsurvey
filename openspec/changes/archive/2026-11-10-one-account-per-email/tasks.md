## 1. Used invitation link

- [x] 1.1 `accept_invitation`: accepted invitation + signed-in member → set `active_org_id`, redirect to `/editor/` without a message; non-member keeps the message
- [x] 1.2 Accepted invitation + signed-out → render `invitation_landing.html` with `used=True`, the workspace, `login_url` (`next` = accept URL)
- [x] 1.3 Template: "already joined" variant with *Sign in* + *Forgot password?*, no *Create Account*

## 2. One account per email

- [x] 2.1 `RegistrationAbuseForm.clean_email`: refuse an existing address (`iexact`), set `email_taken`
- [x] 2.2 `registration_form.html`: sign-in and reset-password links under the email error

## 3. Translations and tests

- [x] 3.1 New strings in every offered catalog (`settings.LANGUAGES`), compile
- [x] 3.2 Tests in `test_workspace_invitation_journey.py` for the used-link scenarios
- [x] 3.3 Tests in `test_registration_abuse_defenses.py` for the address rule
- [x] 3.4 Run the touched modules and the i18n tests; `openspec validate --strict`
