## 1. "Has never collected anything"

- [x] 1.1 Add a model helper for the condition both new transitions depend on: no sessions of the
      survey's own **and** no archived versions. Both halves — sessions move onto the archived header
      when a version is published, so a canonical survey can read zero while the survey has history.
- [x] 1.2 Test it directly: fresh survey, survey with sessions, survey whose sessions moved to an
      archived version, draft copy.

## 2. Lifecycle rules

- [x] 2.1 Add `draft` to the transitions permitted from `published` and `closed`.
- [x] 2.2 Gate both in `can_transition_to` on 1.1, with a refusal message that says why rather than
      just "cannot transition".
- [x] 2.3 Confirm the existing conditions on `testing` and `published` are untouched.

## 3. Draft copies from closed surveys

- [x] 3.1 `editor_create_draft`: accept `closed` as well as `published` (it currently rejects
      everything else with a 400).
- [x] 3.2 `show_edit_published`: same, so the banner offers the route.
- [x] 3.3 Verify `publish_draft` needs no change — it must archive the previous version and leave the
      canonical's status alone, so a closed survey stays closed (design D2). Assert rather than
      assume.

## 4. The banner

- [x] 4.1 The read-only notice always ends in an action: go to the existing draft, create one, or
      return the survey to draft when it has collected nothing.
- [x] 4.2 Add the "Back to Draft" entry to the status dropdown under the same condition.
- [x] 4.3 Word it so returning to draft does not read as a general undo — it is only there while
      nothing has been collected, and it should be obvious that it is about an unpublished mistake.

## 5. Tests

- [x] 5.1 Draft copy can be created from a closed survey; the closed survey is unchanged.
- [x] 5.2 Publishing that draft leaves the canonical `closed`, bumps the version, and archives the
      previous structure and sessions.
- [x] 5.3 `published → draft` succeeds with no sessions and no archived versions.
- [x] 5.4 `published → draft` is refused once a session exists.
- [x] 5.5 `published → draft` is refused when sessions moved to an archived version — the case a
      naive session count would miss.
- [x] 5.6 `closed → draft` succeeds under the same condition.
- [x] 5.7 A second draft copy still cannot be created while one exists.
- [x] 5.8 The structural read-only lock is unchanged: editing a closed survey directly is still 403.

## 6. Verify

- [x] 6.1 Run the full survey suite.
- [x] 6.2 Walk it by hand: close a survey, create a draft from the banner, edit, publish, confirm it
      is still closed and the changes are live, then Reopen.

  Walked on a seeded closed survey with 3 sessions. The banner offered "Create a draft copy", the
  draft was created and edited, and publishing left the canonical `closed` at version 2 with the
  edit in place and all 3 sessions moved onto the archived version. Reopen remains a separate click,
  which is the point.
- [x] 6.3 Walk the accidental-publish path by hand: publish a survey with no responses, return it to
      draft, confirm it is editable.

  Walked, and it caught a defect the test suite could not: my banner comment used `{# #}` across
  three lines, which Django does not strip — it rendered into the page. Fixed here with
  `{% comment %}`. Checking the other templates turned up five more instances of the same thing, two
  of them leaking onto every SEO landing page; filed as **#109** rather than folded in, since those
  templates are unrelated to this change.

## 7. Close the loop

- [x] 7.1 Strike backlog #100 and record that 5 of 7 closed surveys in production were in the dead
      end when this was written.

  Struck, with one refinement recorded on the item: the note there proposed gating the undo on
  `SurveySession.objects.filter(survey=...).exists()` alone, which would be wrong — sessions move to
  the archived header on publish, so a canonical survey can read zero while having history. The
  condition also requires no archived versions.
- [x] 7.2 Note for the reply owed to the reporter: his workaround — copying the survey — is no longer
      necessary, and his sixth point is answered. Worth saying plainly that the route existed but
      only for published surveys, rather than implying he missed it.
