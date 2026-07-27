# Proposal: activation-confirm-post

## Why

Render request logs (2026-07-27) show that **Microsoft Defender Safe Links consumes activation links before the human clicks them**, with plain GET requests from Azure IPs that carry a full Chrome user-agent. Two documented cases from a single day:

- Claire Cameron (DECYP Tasmania, `.gov.au`): scanner GET at 01:01:54 activated the account; her own click at 01:07:33 landed on "Activation Failed" → she re-registered a second account and never signed in.
- `js303643@student.polsl.pl`: identical sequence at 09:03–09:04, also ending in a duplicate account.

15 of the 24 "activated but never logged in" accounts are on institutional domains (government, councils, universities) — precisely the mailboxes behind Microsoft 365, and precisely the outreach targets. The previous change (`activation-funnel-autologin`, archived 2026-07-27) softened the failure into a login redirect, but the original goal — the user lands signed-in without retyping credentials — is still unmet for every Microsoft-hosted mailbox, because the scanner, not the human, consumes the one inactive→active transition that triggers auto-login.

Root cause: `DirectActivationView` activates **on GET**. Upstream django-registration deliberately ships activation as a form POST for exactly this reason; the GET shortcut was a local customization.

## What Changes

- **GET on the activation URL becomes side-effect-free**: it validates the key and renders a confirmation page with a single "Confirm my email" button (or routes expired/invalid keys to the failure page, and already-active accounts to login — unchanged).
- **POST performs the activation** and auto-login. Scanners follow links but do not submit forms, so the inactive→active transition — and with it the auto-login — is consumed by the human.
- Replay semantics unchanged: a key whose account is already active never signs anyone in (bearer-token rationale from the previous change holds for POST too — a form submission proves a human, not the owner).
- **BREAKING** (behavioral): an emailed activation link now requires one extra click. Accepted cost; the alternative (scanner heuristics on IP/UA) is unreliable because the scanner presents a full Chrome UA.

## Capabilities

### New Capabilities

_None._

### Modified Capabilities

- `account-activation`: the auto-login requirement changes from "upon opening the activation URL" to "upon submitting the confirmation form"; a new requirement makes GET side-effect-free.

## Impact

- **Code**: `survey/views.py` (`DirectActivationView.get/post`), new template `django_registration/activation_confirm.html`, test updates in `survey/tests.py` (`ActivationAutoLoginTest`).
- **No migrations, no settings changes, no URL changes** — same endpoint, GET/POST split.
- **Resend flow untouched**: its neutral-response and rate-limit properties are orthogonal.
- **Outreach**: unblocks the institutional segment (DECYP, Flagship, Riverside, LichtBlick, universities) whose activations are currently eaten by Safe Links.
