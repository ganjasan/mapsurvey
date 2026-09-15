# Microsoft sign-in as the second OAuth provider

**Type**: feature
**Priority**: medium
**Area**: backend
**Created**: 2026-08-24

## Description

Add Microsoft as the second social sign-in provider, following up on the `streamline-registration`
change that ships Google-only. The allauth wiring from that change is provider-agnostic, so this is
mostly configuration: enable the allauth Microsoft provider, register the app in Azure AD (redirect
URIs for production and PR previews), add credentials as Render env vars, and list Microsoft as a
processor on `/trust/` and in the DPA.

## Notes

Chosen second because our ICP's institutional half (municipalities, gov agencies, large
consultancies like Stantec/MIG) lives on Microsoft 365. ORCID, GitHub, Facebook remain candidates
after that — Facebook needs app review for the email permission before its button can go live.
Blocked until `streamline-registration` is merged.
