# Design — restore-survey-version

## Context

`publish_draft()` keeps every revision: the old sections (original Question objects,
answers attached) move to an archived header (`status='closed'`,
`canonical_survey` FK). `clone_survey_for_draft(canonical)` clones the *canonical's*
structure into a draft linked via `published_version`. The dashboard "⋯" menu and the
Results version filter already expose archived versions read-only.

## Decisions

### Restore = new draft from archived structure (append-only history)
No in-place rollback: restoring vN creates a draft whose sections/questions are cloned
from the archived vN header. Publishing it produces a NEW version number with the old
structure. Sessions never move; nothing is rewritten. This reuses the entire existing
draft workflow (compat check, force publish, discard) with zero new lifecycle states.

### Structure only; survey-level settings stay current
The draft header copies its settings (name, languages, map defaults, thanks page,
password) from the CANONICAL, exactly as today — only the section/question tree comes
from the archived version. Rationale: archived headers do not preserve map/basemap
settings (publish_draft never copied them), so "restoring" those would resurrect model
defaults, not v2's real settings. "Restore vN" therefore means "restore the
questionnaire of vN", which is what creators regret losing.

### Lineage continuity is the point
Cloning preserves question codes (`regenerate_code=False`), so a question deleted in
v3 returns with its original code and input_type — its lineage becomes current again
and the v1–v2 answers leave the Archived group automatically (cross-version-analytics
machinery). The compat check runs as usual against the current canonical; a question
that exists in v3 but not in v2 will be flagged as deleted (correct — restoring v2
removes it) and force-publish keeps its answers archived.

### Availability rules (same as "Create a draft to edit")
Owner only; canonical must be `published`; no active draft copy (409 otherwise); the
requested version must be an archived member of this survey's family (404 otherwise).

### UI: publishing widget's Version section
Under the existing "vN · Status" row, list `get_version_history()` rows with a
"Restore as draft" POST form per version, rendered only when restore is available.
The widget is owner-only already. On success the user lands in the draft's Build.

## Risks / Trade-offs

- The compat-check dialog may list many "breaking" issues when restoring across a big
  structural gap — accurate, but wordy. Accepted: force-publish copy (updated in
  cross-version-analytics) already explains where answers go.
- Read-only *preview* of an archived structure is deferred (permission resolution on
  archived headers and preview iframe wiring are out of scope; data is already visible
  through the Results version filter).

## Migration

None.
