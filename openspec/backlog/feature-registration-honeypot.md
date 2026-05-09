# Registration Honeypot Field

**Type**: feature
**Priority**: high
**Area**: backend
**Epic**: abuse-prevention
**Created**: 2026-05-08

## Description

Add a hidden honeypot input to the registration form. Real browsers ignore it (CSS `display:none`); naïve bots fill in every field they see. If the honeypot field has a value on POST, silently reject the registration with a 200 OK to avoid signaling that the trap was triggered.

A trivial defense — but it adds zero friction for users, costs nothing to implement, and reliably catches the dumber half of the bot population that doesn't bother with a real headless browser.

## Goals

- Catch unsophisticated bots (the kind that submit form-data without rendering CSS / JS) without any user-visible change.
- Silently log the trigger so we can see how often it fires (data-driven tuning of other defenses).

## Implementation Notes

- Field name should look plausible (`website`, `homepage`, `phone_number_alt`) — not `honeypot_xxx`.
- Hide via inline CSS `style="position:absolute;left:-9999px"` (more reliable than `display:none` against bots that check computed style).
- Add `tabindex="-1"` and `autocomplete="off"` so keyboard / autofill users cannot accidentally fill it.
- Server: any non-empty value → return same success response shape as a real registration but **do not create the account and do not send any email**. The bot thinks it succeeded.
- Log: timestamp, IP, attempted email, attempted username. Goes to a dedicated logger (`abuse.honeypot`).

## Why "200 OK with no account"

- Telling the bot "you failed" lets it iterate. Returning a fake success makes it move on, which is what we want.
- Some implementations return 400. That's noisier but easier to debug. Pick fake-success unless ops finds it confusing.

## Out of Scope

- Honeypots on other forms (login, password reset) — different attack profiles.
- Behavioral analysis (typing speed, mouse-move detection) — overkill for now.

## Related

- Epic: [abuse-prevention](epics/abuse-prevention.md)
- Sibling: [feature-registration-captcha.md](feature-registration-captcha.md), [feature-registration-rate-limiting.md](feature-registration-rate-limiting.md)
