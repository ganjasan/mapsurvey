# GDPR / Security / Trust Page

**Type**: feature
**Priority**: very high
**Area**: general
**Created**: 2026-03-26

## Description

A public-facing page that answers all questions an IT security team would ask before approving Mapsurvey for institutional use. This is the #1 blocker for government and enterprise adoption — Manuel Frost (Berlin Senate) explicitly said his IT security team must approve before he can use the tool officially.

## What the page should cover

### Data Privacy (GDPR)
- No personal data collected from survey respondents
- No login required to fill out a survey
- No cookies for tracking
- No IP addresses stored
- No analytics tied to individual responses
- Respondents are fully anonymous
- Survey creators need an account (email + password only)

### Hosting & Data Residency
- Hosted on Render.com, Frankfurt, Germany (EU) — after migration
- Data stays in the EU
- Provider: Render (SOC 2 Type II certified)

### Open Source & Transparency
- Full source code on GitHub (link)
- MIT/AGPL license (whichever we use)
- Anyone can audit the code

### Security
- HTTPS everywhere
- Django security defaults (CSRF, XSS protection, etc.)
- PostgreSQL with encrypted connections
- No third-party trackers or scripts

### Data Ownership
- Survey creators own their data
- Export available at any time (GeoJSON, CSV)
- Delete account = delete all data

### Who is behind Mapsurvey
- Independent open-source project by Artem Konuchov
- Based in Kyrgyzstan
- Not affiliated with any government or corporation

## Notes

- Source: Manuel Frost (manu04) — "If the data cannot be collected anonymously, I am not allowed to use it"
- His IT security team is "always very skeptical of unknown freeware tools"
- URL: /security/ or /trust/ (not just /privacy/ — broader scope)
- Consider adding a downloadable PDF version for IT teams to circulate internally
- Consider a Data Processing Agreement (DPA) template for institutional users
