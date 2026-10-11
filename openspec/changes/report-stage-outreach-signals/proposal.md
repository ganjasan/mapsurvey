# Proposal — report-stage outreach signals

## Why

The outreach that converts best today is manual and depends on noticing: when a survey has
stopped collecting and its creator starts turning the answers into a report, the owner writes
to them, offers to tell their story on the blog and sends a materials archive built the way
the `survey-report` skill describes. It produces the "wow" that the Pro tier is supposed to
sell, and it works on exactly the creators who would pay (public bodies, consultancies,
NGOs). The platform has every fact needed to spot that moment — the collection curve, the
status change to `closed`, the creator opening Responses, the creator exporting the data —
but the one that says "they are building the report right now", the export, lives only in
PostHog, and nothing watches any of them. The owner finds these surveys by reading the
dashboard by hand, late or not at all.

## What Changes

- **Persist creator return-to-data actions.** `responses_viewed` and `data_exported` keep
  going to PostHog and additionally leave one row per creator, survey, action and day in the
  application database, so detection does not depend on an analytics vendor and survives
  its outages.
- **Detect the report stage once a day.** A scheduled job scores every published or closed
  survey whose creator is a real (non-staff) account against a weighted table of
  sub-signals — a data export, a close, a flattened collection curve, repeated Responses
  visits, a geo-rich answer set, an institutional creator, a Pro-interest answer — above a
  minimum volume of external, non-empty responses. A data export is also a trigger on its
  own: with the volume prerequisite met, it fires without waiting for the curve. A survey
  fires at most once; later runs only add sub-signals to the existing record.
- **Record and deliver the signal.** Each firing is a row with a status workflow
  (`new` → `contacted` / `dismissed` / `won`) edited by staff in the admin, a `signal` note on
  the creator's dossier timeline, a PostHog event (ids only), and a line in one daily digest
  mail to the owner that names the survey, the creator, the sub-signals and deep links to
  the dossier, the Responses page and the data export.
- **Show it on the funnel dashboard.** A third action list, "Report stage", next to the two
  that already exist, with the open signals and their status.
- **Calibrate before trusting.** The detector has a dry run as of a past date, so the weights
  can be checked against the surveys the owner already reached out to this way.

Out of scope: generating the materials archive automatically (the next step, a command over
the export bundle) and showing anything to the creator (the in-product "report kit" that the
Pro tier would sell). This change only tells the owner whom to write to, and when.

## Capabilities

### New Capabilities
- `creator-return-activity`: the persisted record of a creator returning to a survey's data
  (Responses page, data export), one row per creator, survey, action and day.
- `report-stage-signals`: detection of surveys entering the reporting stage, the scoring
  rules, the once-per-survey signal record with its status workflow, and the deliveries
  (digest mail, dossier note, product event).

### Modified Capabilities
- `creator-distribution-events`: the return-to-data requirement now also persists a row
  (the PostHog emission is unchanged).
- `creator-funnel-dashboard`: the action lists requirement gains a third list, "Report stage";
  the no-new-table rule is restated to allow the two tables this change adds, which hold
  forward-only facts the dashboard cannot derive from existing rows.

## Impact

- `survey/models.py`: two new tables, `CreatorSurveyActivity` and `OutreachSignal`, plus a
  migration. Nothing on `SurveySession` or `SurveyEvent` (respondent data stays apart).
- `survey/product_events.py`: the two server-side emit sites in `analytics_views.py` and
  `views.py` go through one helper that persists and emits.
- New module `survey/report_stage.py` (pure scoring over a weights table, like
  `content_screening.py`) and management command `detect_report_stage` with `--dry-run`
  and `--as-of`; a Render cron entry on the existing image.
- `survey/funnel.py` + `templates/admin/funnel_dashboard.html`: the "Report stage" list.
- `survey/admin.py`: `OutreachSignal` admin with the status workflow; `survey/mail.py`
  templates for the digest, sent to `OUTREACH_SIGNAL_EMAIL` (default `CONTACT_EMAIL`).
- `CreatorNote` rows of kind `signal` written idempotently via `source_path`.
- Tests in `survey/tests.py`; `render.yaml` cron; `CLAUDE.md` paragraph.
- No creator-facing change, no respondent-facing change, no new dependency.
