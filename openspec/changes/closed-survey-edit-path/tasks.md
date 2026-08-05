## 1. "Has never collected anything"

- [ ] 1.1 Add a model helper for the condition both new transitions depend on: no sessions of the
      survey's own **and** no archived versions. Both halves — sessions move onto the archived header
      when a version is published, so a canonical survey can read zero while the survey has history.
- [ ] 1.2 Test it directly: fresh survey, survey with sessions, survey whose sessions moved to an
      archived version, draft copy.

## 2. Lifecycle rules

- [ ] 2.1 Add `draft` to the transitions permitted from `published` and `closed`.
- [ ] 2.2 Gate both in `can_transition_to` on 1.1, with a refusal message that says why rather than
      just "cannot transition".
- [ ] 2.3 Confirm the existing conditions on `testing` and `published` are untouched.

## 3. Draft copies from closed surveys

- [ ] 3.1 `editor_create_draft`: accept `closed` as well as `published` (it currently rejects
      everything else with a 400).
- [ ] 3.2 `show_edit_published`: same, so the banner offers the route.
- [ ] 3.3 Verify `publish_draft` needs no change — it must archive the previous version and leave the
      canonical's status alone, so a closed survey stays closed (design D2). Assert rather than
      assume.

## 4. The banner

- [ ] 4.1 The read-only notice always ends in an action: go to the existing draft, create one, or
      return the survey to draft when it has collected nothing.
- [ ] 4.2 Add the "Back to Draft" entry to the status dropdown under the same condition.
- [ ] 4.3 Word it so returning to draft does not read as a general undo — it is only there while
      nothing has been collected, and it should be obvious that it is about an unpublished mistake.

## 5. Tests

- [ ] 5.1 Draft copy can be created from a closed survey; the closed survey is unchanged.
- [ ] 5.2 Publishing that draft leaves the canonical `closed`, bumps the version, and archives the
      previous structure and sessions.
- [ ] 5.3 `published → draft` succeeds with no sessions and no archived versions.
- [ ] 5.4 `published → draft` is refused once a session exists.
- [ ] 5.5 `published → draft` is refused when sessions moved to an archived version — the case a
      naive session count would miss.
- [ ] 5.6 `closed → draft` succeeds under the same condition.
- [ ] 5.7 A second draft copy still cannot be created while one exists.
- [ ] 5.8 The structural read-only lock is unchanged: editing a closed survey directly is still 403.

## 6. Verify

- [ ] 6.1 Run the full survey suite.
- [ ] 6.2 Walk it by hand: close a survey, create a draft from the banner, edit, publish, confirm it
      is still closed and the changes are live, then Reopen.
- [ ] 6.3 Walk the accidental-publish path by hand: publish a survey with no responses, return it to
      draft, confirm it is editable.

## 7. Close the loop

- [ ] 7.1 Strike backlog #100 and record that 5 of 7 closed surveys in production were in the dead
      end when this was written.
- [ ] 7.2 Note for the reply owed to the reporter: his workaround — copying the survey — is no longer
      necessary, and his sixth point is answered. Worth saying plainly that the route existed but
      only for published surveys, rather than implying he missed it.
