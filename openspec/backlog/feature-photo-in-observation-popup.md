# Photo attachment inside the observation popup

**Type**: feature
**Priority**: medium
**Area**: backend
**Created**: 2026-08-23

## Description

A sub-question that takes a photo from the phone camera and attaches it to the feature the
respondent just placed, so the picture rides along in the GeoJSON export as a property.

Verification is the point: "is that squirrel actually albino", "what does the damage look
like", "which asset is this". Every field tool in the competitive set has it, and
Survey123's 10 MB attachment cap is the single most complained-about limit in the r/gis
thread ([[features-from-field-gis-feedback]]) — a cheap place to be visibly better.

## Notes

- Blocked in practice by media storage: files land on the Render disk that already pins us
  to one instance with a 502 on every deploy ([[project-deploy-downtime-disk]]). Field
  volumes make this worse fast — do FD-11 (S3) first or in the same change.
- Client-side downscale before upload; a modern phone photo is 5-12 MB and volunteers are
  on cellular.
- Epic: field-data-collection (FD-4)
