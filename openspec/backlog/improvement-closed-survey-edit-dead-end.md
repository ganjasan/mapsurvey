# A closed survey is a dead end — no offered way back to editing

**Type**: improvement
**Priority**: high
**Area**: frontend
**Created**: 2026-08-04

## Description

Lifecycle transitions allow `published → closed → published | archived` and offer no path back to
`draft` (`survey/models.py:83-89`). That is deliberate: a survey with live responses must not be
edited in place, and versioning provides the correct route via a draft copy.

The problem is that the route is only advertised for `published`. `show_edit_published` requires
`survey.status == 'published'` (`survey/editor_views.py:146-148`), so on a **closed** survey the
read-only banner renders with no action at all: no "Create a draft copy", no "Go to draft", and a
status dropdown offering only Reopen and Archive. The editor is locked and the UI names no way out.

The actual sequence — Reopen, *then* create a draft copy — is not discoverable, and reopening a
closed survey to edit it looks wrong enough that a careful user will not try it. A user who clicks
Publish to see what happens, then closes the survey to undo that, lands in this state permanently.

## Notes

- Reported by: Manuel Frost (manu04, Berlin Senate) 2026-08-04 — "I clicked on the publish-Button
  to see what happened. After that, i can't go back. So I closed the survey... Is there any
  possibility to unlock the survey to the edit-mode? I fixed that with a work-around: I make a copy
  to new one." The workaround was forced on him by the missing affordance, and it costs him the
  responses and the survey URL.
- Minimal fix: allow the draft-copy path for `closed` as well as `published` — the versioning
  machinery is status-agnostic, only the template flag is not.
- Worth pairing with a second, smaller gap this exposes: a survey published by accident with zero
  responses has no cheap undo. Consider allowing `published → draft` when
  `SurveySession.objects.filter(survey=...).exists()` is false, which covers the "clicked to see
  what happens" case directly and needs no draft copy at all.
- Also review the wording of the read-only banner: it states the lock without naming the next
  action, which is what left him stuck.
