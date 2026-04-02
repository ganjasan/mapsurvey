# QR code poster generator

**Type**: feature
**Priority**: medium
**Area**: frontend
**Created**: 2026-04-02

## Description

Generate a print-ready PDF poster with a QR code linking to the survey, plus the survey title, brief description, and available languages. Allows planners to quickly produce branded materials for intercept survey deployments at grocery stores, farmers markets, schools, and community events.

## Notes

- See [UC-03: Intercept Survey at Public Location](../docs/use-cases/uc03-intercept-survey.md)
- QR code should encode survey URL with optional location parameter
- Poster template: A4/Letter, customizable accent color, township logo upload
- Multi-language: list available survey languages on the poster
- PDF generated server-side or client-side (e.g., jsPDF + qrcode.js)
