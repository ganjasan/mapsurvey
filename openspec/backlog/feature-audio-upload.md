# Media upload question type (image, audio, video)

**Type**: feature
**Priority**: medium
**Area**: backend
**Created**: 2026-03-26
**Updated**: 2026-08-04 — broadened from audio-only to image/audio/video; priority raised from low

## Description

Add a file-upload input type so respondents can attach media to their response. Relevant for
soundscape research, oral history, accessibility, and — the common case — photographing the thing
being mapped.

Note that the existing `image` type is **not** this: it renders an image to the respondent
(`ShowImageWidget`, `survey/forms.py:209`), it does not accept one. There is currently no way for a
respondent to upload a file of any kind. The naming collision is itself a discoverability problem
and should be resolved when this is built.

## Notes

- Source: Manuel Frost (manu04) — originally 2026-03-26 for audio (his survey is about acoustic
  quality of urban spaces, audio samples would be valuable); repeated 2026-08-04 asking for
  image, audio and video together: "The ability to upload images, audio, or videos is still
  missing."
- Also requested by field-GIS users, where a photo attached to a mapped point is table stakes —
  see the field-collection competitor set (Fulcrum, Survey123, QField all have it).
- Design decisions to settle before building: storage (S3 is already wired behind `USE_S3`),
  size and type limits, virus scanning, whether media is included in the ZIP export or linked,
  and what a public results map does with respondent-submitted media. The moderation question is
  real — an open survey accepting arbitrary uploads is an abuse surface.
- Attaching media to a **sub-question** of a geo question is the highest-value slice: that is how
  attributes of a mapped object are modelled, so "photo of this location" falls out of it.
