# Fix primary-language duplicate fields

## Why

The editor renders a translation input for **every** entry of `available_languages`, including
the primary one — so every title/name/subtext/choice exists twice: the base field and the
"translation" into the survey's own primary language. AI drafts make it worse: materialization
writes the same text into both. The two copies silently diverge as the creator edits one of
them, and respondents see an unpredictable mix (`get_translated_*` prefers a non-empty
translation, else falls back to base).

Observed in production on 2026-08-19 (survey 465, PROGRAMA RAICES, first Spanish-speaking AI
user): 61 rageclicks + 19 dead clicks in one editing session, 31 minutes spent editing fields
respondents never see, published with section 3 showing the author's title next to a stale AI
subheading. The trilingual survey 467 carries the same duplicate rows (pt translation ==
base, character for character) plus the second failure mode: a manually added question with no
translation rows at all, shown in Portuguese to es/en respondents mid-survey — and the editor
never warns. Finally, the same session showed the AI misreading the brief's role framing: the
creator wanted a self-registration registry ("register YOUR business"), the
`citizen_science` prompt guidance ("respondents record what they observed") pushed the model
into an observer/consumer survey, forcing a full rewrite of two of three sections.

## What Changes

- **Primary language lives in base fields only.** Translation inputs (section form, question
  modal, choices table columns) render only for `available_languages[1:]`. A single-language
  survey shows no translation fields at all.
- **Base fields are labeled with the primary language** (e.g. "Título (Português)"), so a
  multilingual author doesn't mistake base for a "neutral default" text.
- **Save handlers ignore `translation_<primary>_*` POST keys** (section, question, choices),
  so stale open forms / HTMX tails cannot resurrect primary-language translation rows.
- **AI materialization stops emitting primary-language translation rows**; the primary text
  goes to base fields only. Choice name storage follows the same model (exact JSON shape in
  design — the flat-vs-locale-dict duality between manual and AI-created choices is part of
  the bug).
- **Data migration** collapses existing primary-language translation rows into base fields
  with the rule "non-empty translation wins" — exactly what respondents currently see, so the
  migration is behavior-preserving for respondents while removing the duplicate. Covers
  sections, questions, and primary keys inside choice name dicts, for any number of languages.
- **Translation completeness indicator**: the editor surfaces a per-question/per-section
  marker when any text (name, subtext, title, subheading, choice names) is missing a
  translation for one of `available_languages[1:]`, and the publish flow warns with the list
  of gaps. Base-language fallback stops silently masking holes from the author.
- **AI prompt tuning**: recognize the self-registration / inventory pattern (respondents map
  something they own or represent — their business, their project, their home) and frame
  questions in the first person about the respondent's own place instead of the observer
  framing; adjust `citizen_science` guidance which currently hard-codes the observer role.
  Update `docs/research/survey-design-rules.md` together with the prompt (they must not
  drift, per `survey/ai/prompts.py` header).

**BREAKING (data)**: primary-language `SurveySectionTranslation`/`QuestionTranslation` rows
are deleted by the migration after being folded into base fields. Respondent-visible text is
unchanged by construction; anything that read those rows directly must use base fields.

## Capabilities

### New Capabilities

- `translation-completeness`: editor-side visibility of missing translations — per-entity
  indicators for gaps in `available_languages[1:]` and a pre-publish warning listing them.

### Modified Capabilities

- `survey-content-translation`: requirement changes — primary-language content lives in base
  fields only; translation rows exist only for non-primary languages; fallback semantics of
  `get_translated_*` stay (translation if non-empty, else base) but primary rows no longer
  exist to shadow base.
- `survey-editor`: translation inputs render for non-primary languages only; base fields are
  labeled with the primary language; choices editor columns follow the same rule.
- `ai-survey-generation`: materialization requirement "create translation rows … for every
  language" changes to "for every non-primary language; base fields carry the primary
  language"; prompt requirements gain the self-registration/inventory framing rule. NOTE:
  this capability's spec currently lives as a delta in the completed-but-unarchived
  `ai-survey-generator` change — archive it first or coordinate the delta.

## Impact

- `survey/editor_views.py` — `_save_section_translations`, `_save_question_translations`,
  choices parsing, language context passed to templates.
- `survey/templates/editor/partials/question_form_modal.html` and the section form partial —
  translation blocks, choices table columns, base-field labels, completeness markers.
- `survey/ai/materialize.py` (`_translations`), `survey/ai/prompts.py`
  (`USE_CASE_GUIDANCE`, `DESIGN_RULES`), `docs/research/survey-design-rules.md`.
- New data migration over `SurveySectionTranslation`, `QuestionTranslation`, and
  `Question.choices` JSON.
- Publish flow (lifecycle partials) — pre-publish translation-gap warning.
- Tests: editor save paths, materialization, migration (GIVEN/WHEN/THEN), template guard
  test after partial edits.
- Repairs production surveys 465 and 467 in place via the migration.
