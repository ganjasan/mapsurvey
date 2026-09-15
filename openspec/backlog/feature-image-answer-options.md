# Image as an answer option (choice / multichoice with pictures)

**Type**: feature
**Priority**: low
**Area**: frontend
**Created**: 2026-08-31

## Description

"Which of these three bench designs?" — a choice question where each option is a picture.
Maptionnaire "Select image" works for multiple choice, checkboxes, rankings and polls.
`OptionChoice` already has no image field; `image` question type exists but shows one
picture and collects nothing. Design-variant questions are common in the park/plaza
redesign surveys our planners run.

## Scope Sketch

- `OptionChoice.image` (public artwork tier in S3, same upload path as question images).
- Render as a card grid for `choice` / `multichoice` / ranking when any option has an
  image; text-only otherwise.
- Charts: option label = caption, thumbnail in the legend.
- Round-trips ZIP export/import (`choices/*.jpg` next to `survey.json`).
