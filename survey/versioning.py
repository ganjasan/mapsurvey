"""
Survey versioning module.

Provides draft-copy workflow for published surveys:
- clone_survey_for_draft(): Create a draft copy of a published survey
- check_draft_compatibility(): Verify backward compatibility before publish
- publish_draft(): Atomically publish a draft copy as a new version
"""
from dataclasses import dataclass, field

from django.conf import settings
from django.db import transaction
from django.db.models import Q

from .cloning import clone_question
from .models import (
    SurveyHeader, SurveySection, SurveySectionTranslation,
    Question, QuestionTranslation, Answer, SurveySession,
    SurveyCollaborator,
)


class IncompatibleDraftError(Exception):
    """Raised when a draft has breaking compatibility issues and force is not set."""
    def __init__(self, issues):
        self.issues = issues
        super().__init__(f"{len(issues)} breaking compatibility issue(s) found")


# ─── Version-family scope ────────────────────────────────────────────────────
#
# publish_draft() moves the old sections *and all sessions* onto a new archived
# header, so any read that filters by a single SurveyHeader goes blind after a
# publish. Every creator-facing count/aggregate must go through these helpers.

def canonical_of(survey):
    """Return the canonical survey for any version or draft copy.

    Two links lead home: an archived version points at the canonical via
    canonical_survey, a draft copy via published_version. Following only the
    first left a draft as its own canonical, so every scope built from here
    described the draft's preview traffic instead of the survey's responses.
    """
    return survey.canonical_survey or survey.published_version or survey


def family_ids(survey):
    """Return the set of SurveyHeader ids in the survey's version family.

    The family is the canonical survey plus its archived version copies
    (linked via the canonical_survey FK). A draft copy is deliberately NOT a
    member: it owns only test sessions, which must never reach a real count or
    the public results page. Use family_ids_with_draft() where the draft's own
    sessions are legitimately in play.
    """
    canonical = canonical_of(survey)
    ids = {canonical.id}
    ids.update(
        SurveyHeader.objects
        .filter(canonical_survey=canonical)
        .values_list('id', flat=True)
    )
    return ids


def draft_copy_of(survey):
    """The family's draft copy, or None."""
    if survey.is_draft_copy:
        return survey
    return canonical_of(survey).get_draft_copy()


def family_ids_with_draft(survey):
    """Family ids plus the draft copy — every session a creator may act on.

    Backs the session-level guards in analytics: a session listed under the
    draft filter must also be openable, taggable and deletable, while a
    session from an unrelated survey stays rejected.
    """
    ids = family_ids(survey)
    draft = draft_copy_of(survey)
    if draft is not None:
        ids.add(draft.id)
    return ids


def family_sessions(survey, include_deleted=False):
    """Sessions across the whole version family (each counted exactly once —
    a session FK-points at exactly one version header)."""
    qs = SurveySession.objects.filter(survey_id__in=family_ids(survey))
    if not include_deleted:
        qs = qs.filter(is_deleted=False)
    return qs


# ─── The `version` request filter ────────────────────────────────────────────
#
# Analytics and the data export both accept ?version=. They used to parse it
# separately and disagreed: different defaults, and 'latest' narrowed one
# surface while widening the other. One resolver serves both — the shapes they
# need (ids for analytics, ordered headers for the export) come off one scope.

# The filter value that selects the family's draft copy. Never the default:
# preview traffic is only ever reported when explicitly asked for.
DRAFT_SCOPE = 'draft'


@dataclass(frozen=True)
class VersionScope:
    """The version(s) a `version` filter value resolves to.

    value:   the normalised filter value — 'all', 'vN', or 'draft'
    headers: the SurveyHeaders in scope, canonical first then archived
             newest-first (the export writes one file set per header, in order)
    """
    value: str
    headers: list = field(default_factory=list)

    @property
    def ids(self):
        return {header.id for header in self.headers}

    @property
    def is_family(self):
        """True when the scope spans more than one version."""
        return len(self.headers) > 1


def family_headers(survey):
    """The family's SurveyHeaders: canonical first, then archived newest-first."""
    canonical = canonical_of(survey)
    archived = list(
        SurveyHeader.objects
        .filter(canonical_survey=canonical)
        .order_by('-version_number')
    )
    return [canonical] + archived


def _requested_version_number(version, canonical):
    """The version number a filter value names, or None for the whole family.

    'latest' is an alias for the canonical version — resolved here rather than
    crashing inside the int() parse, which is how the two surfaces used to
    diverge. Anything unrecognised returns None, i.e. the default scope.
    """
    if not version:
        return None
    value = str(version).strip().lower()
    if value in ('', 'all'):
        return None
    if value == 'latest':
        return canonical.version_number
    try:
        return int(value.lstrip('v'))
    except (TypeError, ValueError):
        return None


def resolve_version_scope(survey, version=None):
    """Resolve a `version` filter value to a VersionScope.

    Missing, 'all', or unresolvable values → the whole family. 'latest', 'vN'
    and 'N' → that single version, when the family has one with that number.
    'draft' → the family's draft copy, when it has one.
    """
    canonical = canonical_of(survey)
    if str(version or '').strip().lower() == DRAFT_SCOPE:
        draft = draft_copy_of(canonical)
        if draft is not None:
            return VersionScope(value=DRAFT_SCOPE, headers=[draft])
    headers = family_headers(canonical)
    num = _requested_version_number(version, canonical)
    if num is not None:
        for header in headers:
            if header.version_number == num:
                return VersionScope(value=f'v{num}', headers=[header])
    return VersionScope(value='all', headers=headers)


def lineage_map(survey, include_draft=False):
    """Build the question-lineage map for a survey's version family.

    A lineage groups the questions that share (code, input_type) across the
    family's versions — the same logical question carried through publishes
    (clones keep codes; an input_type change intentionally breaks the lineage
    so incompatible answer shapes are never merged).

    include_draft adds the draft copy's questions to the lineages they belong
    to. A draft's questions are clones — same code, new ids — so without them a
    draft-scoped read finds the right columns and no answers at all. Off by
    default: nothing in a published scope may aggregate over preview data.

    Returns an ordered dict {(code, input_type): {
        'questions':    [Question, ...]   # newest version first
        'question_ids': [int, ...],
        'current':      Question | None,  # the canonical version's object
        'versions':     'v2' or 'v1–v3',  # display range label ('draft' when
                                          # the lineage exists only in a draft)
    }} with current-structure lineages first (in canonical order), then
    archived-only lineages (newest first).
    """
    canonical = canonical_of(survey)
    ids = family_ids(canonical)
    draft = draft_copy_of(canonical) if include_draft else None
    if draft is not None:
        ids = ids | {draft.id}

    questions = (
        Question.objects
        .filter(survey_section__survey_header_id__in=ids)
        .select_related('survey_section__survey_header')
        .order_by('-survey_section__survey_header__version_number', 'order_number')
    )

    lineages = {}
    for q in questions:
        key = (q.code, q.input_type)
        header = q.survey_section.survey_header
        entry = lineages.setdefault(key, {
            'questions': [], 'question_ids': [], 'current': None, '_vers': [],
        })
        entry['questions'].append(q)
        entry['question_ids'].append(q.id)
        # A draft carries a placeholder version_number (it becomes a version
        # only at publish), so it must not stretch the displayed range.
        if not header.is_draft_copy:
            entry['_vers'].append(header.version_number)
        if header.id == canonical.id:
            entry['current'] = q

    for entry in lineages.values():
        if entry['_vers']:
            lo, hi = min(entry['_vers']), max(entry['_vers'])
            entry['versions'] = f'v{lo}' if lo == hi else f'v{lo}–v{hi}'
        else:
            entry['versions'] = DRAFT_SCOPE
        del entry['_vers']

    # Current lineages first (canonical question order), archived after.
    current = {k: v for k, v in lineages.items() if v['current'] is not None}
    current = dict(sorted(current.items(), key=lambda kv: kv[1]['current'].order_number))
    archived = {k: v for k, v in lineages.items() if v['current'] is None}
    return {**current, **archived}


def clone_survey_for_draft(canonical, structure_source=None):
    """
    Create a draft copy of a published survey.

    Clones sections, questions (with same codes), choices, translations,
    sub-questions, and collaborators. The draft is linked to the canonical
    via published_version FK.

    structure_source: SurveyHeader whose section/question tree to clone —
    defaults to the canonical itself. Pass an archived version to restore an
    old questionnaire as a new draft ("git revert": publishing it creates a
    NEW version with the old structure; history is never rewritten). Header
    settings and collaborators always come from the canonical — archived
    headers never carried map/basemap settings, so cloning those from the
    source would resurrect model defaults.

    Returns the draft SurveyHeader.
    """
    structure_source = structure_source or canonical
    # Build draft name: "[draft] " prefix, truncated to 45 chars
    draft_name = f"[draft] {canonical.name}"[:45]

    draft = SurveyHeader.objects.create(
        organization=canonical.organization,
        created_by=canonical.created_by,
        name=draft_name,
        redirect_url=canonical.redirect_url,
        available_languages=canonical.available_languages,
        visibility=canonical.visibility,
        thanks_html=canonical.thanks_html,
        password_hash=canonical.password_hash,
        basemaps=canonical.basemaps,
        default_basemap=canonical.default_basemap,
        start_map_postion=canonical.start_map_postion,
        start_map_zoom=canonical.start_map_zoom,
        use_geolocation=canonical.use_geolocation,
        show_branding=canonical.show_branding,
        style_settings=canonical.style_settings,
        status="draft",
        published_version=canonical,
    )

    # Clone collaborators
    for collab in SurveyCollaborator.objects.filter(survey=canonical):
        SurveyCollaborator.objects.create(
            user=collab.user,
            survey=draft,
            role=collab.role,
        )

    # Clone sections and build old->new mapping for linked list resolution
    sections = SurveySection.objects.filter(survey_header=structure_source)
    old_to_new_section = {}

    for section in sections:
        new_section = SurveySection.objects.create(
            survey_header=draft,
            is_head=section.is_head,
            name=section.name,
            title=section.title,
            subheading=section.subheading,
            code=section.code,
            start_map_postion=section.start_map_postion,
            start_map_zoom=section.start_map_zoom,
            use_geolocation=section.use_geolocation,
            override_basemap=section.override_basemap,
            # next/prev resolved after all sections created
        )
        old_to_new_section[section.pk] = new_section

        # Clone section translations
        for trans in SurveySectionTranslation.objects.filter(section=section):
            SurveySectionTranslation.objects.create(
                section=new_section,
                language=trans.language,
                title=trans.title,
                subheading=trans.subheading,
            )

        # Clone questions (top-level only, sub-questions handled recursively)
        for question in Question.objects.filter(
            survey_section=section, parent_question_id__isnull=True
        ).order_by('order_number'):
            clone_question(
                question,
                target_section=new_section,
                parent=None,
                regenerate_code=False,  # versioning preserves codes for compatibility checks
                name_suffix=None,
                copy_sub_questions=True,
            )

    # Resolve section linked list
    for old_section in sections:
        new_section = old_to_new_section[old_section.pk]
        if old_section.next_section_id and old_section.next_section_id in old_to_new_section:
            new_section.next_section = old_to_new_section[old_section.next_section_id]
        if old_section.prev_section_id and old_section.prev_section_id in old_to_new_section:
            new_section.prev_section = old_to_new_section[old_section.prev_section_id]
        new_section.save()

    return draft


# ─── Live editing (change edit-live-survey) ─────────────────────────────────
#
# A published or closed survey takes SAFE edits in place — wording, help text,
# translations, added options, map and display settings — because none of them
# can orphan an answer. STRUCTURAL edits go to the draft copy, which the editor
# calls "unpublished changes". The rule is by kind of edit, not by whether the
# target happens to have answers today, so it stays explainable in a sentence.
# Removing a choice is the one data-dependent case, and it follows the same rule
# check_draft_compatibility applies at publish time (answered codes only).

def live_editing_enabled():
    return getattr(settings, 'LIVE_SURVEY_EDITING', False)


def is_live(survey):
    """True for a published/closed canonical survey — the one respondents see."""
    return survey.status in ('published', 'closed') and not survey.is_draft_copy


def answered_choice_counts(question):
    """{choice code: number of answers that selected it} for one question row."""
    counts = {}
    for selected in (
        Answer.objects.filter(question=question, selected_choices__isnull=False)
        .values_list('selected_choices', flat=True)
    ):
        for code in set(selected or ()):
            counts[code] = counts.get(code, 0) + 1
    return counts


def removed_answered_choices(question, old_choices, new_choices):
    """Choices dropped by an edit that answers still point at.

    Returns [(code, label, answer_count)] — empty when the edit is safe.
    """
    old = {c.get('code'): c for c in (old_choices or []) if isinstance(c, dict)}
    new_codes = {c.get('code') for c in (new_choices or []) if isinstance(c, dict)}
    removed = set(old) - new_codes
    if not removed:
        return []
    counts = answered_choice_counts(question)
    return [
        (code, old[code].get('name') or str(code), counts[code])
        for code in sorted(removed, key=str) if counts.get(code)
    ]


def structural_question_changes(before, after, removed_choices=()):
    """Reasons an edit of `before` into `after` is structural on a live survey.

    `before` is a dict snapshot taken before the form touched the instance
    (ModelForm validation mutates it); `after` is the unsaved Question.
    """
    reasons = []
    if before['input_type'] != after.input_type:
        reasons.append('the question type')
    if before['layer_id'] != after.layer_id:
        reasons.append('the layer')
    if (before['visibility_rule'] or None) != (after.visibility_rule or None):
        reasons.append('the visibility rule')
    for _code, label, count in removed_choices:
        reasons.append(f'the option “{label}” ({count} answer{"s" if count != 1 else ""})')
    return reasons


def question_snapshot(question):
    return {
        'input_type': question.input_type,
        'layer_id': question.layer_id,
        'visibility_rule': question.visibility_rule,
        'choices': list(question.choices or []),
    }


def structural_section_changes(before, after):
    reasons = []
    if before['code'] != after.code:
        reasons.append('the section code')
    if (before['visibility_rule'] or None) != (after.visibility_rule or None):
        reasons.append('the visibility rule')
    return reasons


def section_snapshot(section):
    return {'code': section.code, 'visibility_rule': section.visibility_rule}


def structural_edit_message(reasons):
    return (
        'Changing ' + ', '.join(reasons) + ' would change the structure of a live survey. '
        'Start unpublished changes to make this edit; respondents keep the current '
        'survey until you publish them.'
    )


def check_draft_compatibility(draft, canonical):
    """
    Check backward compatibility between draft and canonical.

    Detects breaking changes that would orphan existing answers:
    - Deleted questions (by code) that have answers
    - Changed input_type on questions that have answers
    - Removed choice codes on questions where answers use those codes

    Returns list of breaking issue dicts.
    """
    issues = []

    # Get question codes and their properties from both versions
    canonical_questions = {}
    for q in Question.objects.filter(
        survey_section__survey_header=canonical
    ):
        canonical_questions[q.code] = q

    draft_codes = set(
        Question.objects.filter(
            survey_section__survey_header=draft
        ).values_list('code', flat=True)
    )

    for code, canonical_q in canonical_questions.items():
        answer_count = Answer.objects.filter(question=canonical_q).count()
        if answer_count == 0:
            continue

        # Check if question was deleted in draft
        if code not in draft_codes:
            issues.append({
                'type': 'deleted_question',
                'question_code': code,
                'question_name': canonical_q.name,
                'answer_count': answer_count,
            })
            continue

        # Get the draft version of this question
        draft_q = Question.objects.filter(
            survey_section__survey_header=draft, code=code
        ).first()

        # Check input_type change
        if draft_q and draft_q.input_type != canonical_q.input_type:
            issues.append({
                'type': 'changed_input_type',
                'question_code': code,
                'question_name': canonical_q.name,
                'old_type': canonical_q.input_type,
                'new_type': draft_q.input_type,
                'answer_count': answer_count,
            })

        # Check removed choice codes
        if draft_q and canonical_q.choices and draft_q.choices is not None:
            old_codes = {c['code'] for c in canonical_q.choices}
            new_codes = {c['code'] for c in draft_q.choices}
            removed_codes = old_codes - new_codes

            if removed_codes:
                affected_count = sum(
                    n for c, n in answered_choice_counts(canonical_q).items()
                    if c in removed_codes
                )
                if affected_count > 0:
                    issues.append({
                        'type': 'removed_choice_codes',
                        'question_code': code,
                        'question_name': canonical_q.name,
                        'removed_codes': list(removed_codes),
                        'answer_count': affected_count,
                    })

    return issues


def publish_draft(draft, force=False):
    """
    Publish a draft copy as a new version of the canonical survey.

    Atomically:
    1. Create archived SurveyHeader for current canonical structure
    2. Move sections from canonical to archived
    3. Move sessions from canonical to archived
    4. Move sections from draft to canonical
    5. Copy settings from draft to canonical
    6. Increment canonical.version_number
    7. Delete draft

    Raises IncompatibleDraftError if breaking issues found and force=False.
    Returns the canonical survey.
    """
    canonical = draft.published_version
    if canonical is None:
        raise ValueError("Draft has no published_version — not a valid draft copy")

    # Run compatibility check
    issues = check_draft_compatibility(draft, canonical)
    if issues and not force:
        raise IncompatibleDraftError(issues)

    with transaction.atomic():
        # 1. Create archived version
        archived = SurveyHeader.objects.create(
            organization=canonical.organization,
            created_by=canonical.created_by,
            name=canonical.name,
            redirect_url=canonical.redirect_url,
            available_languages=canonical.available_languages,
            visibility=canonical.visibility,
            thanks_html=canonical.thanks_html,
            show_branding=canonical.show_branding,
            style_settings=canonical.style_settings,
            status='closed',
            is_canonical=False,
            canonical_survey=canonical,
            version_number=canonical.version_number,
        )

        # 2. Move sections from canonical to archived
        SurveySection.objects.filter(
            survey_header=canonical
        ).update(survey_header=archived)

        # 3. Move sessions from canonical to archived
        SurveySession.objects.filter(
            survey=canonical
        ).update(survey=archived)

        # 4. Move sections from draft to canonical
        SurveySection.objects.filter(
            survey_header=draft
        ).update(survey_header=canonical)

        # 5. Copy settings from draft to canonical
        canonical.available_languages = draft.available_languages
        canonical.visibility = draft.visibility
        canonical.redirect_url = draft.redirect_url
        canonical.thanks_html = draft.thanks_html
        canonical.basemaps = draft.basemaps
        canonical.default_basemap = draft.default_basemap
        canonical.start_map_postion = draft.start_map_postion
        canonical.start_map_zoom = draft.start_map_zoom
        canonical.use_geolocation = draft.use_geolocation
        canonical.show_branding = draft.show_branding

        # 6. Increment version
        canonical.version_number += 1
        canonical.save()

        # 7. Delete draft (sections already moved, so just the header)
        # Remove any test sessions created against the draft
        SurveySession.objects.filter(survey=draft).delete()
        draft.delete()

    return canonical
