"""
Survey versioning module.

Provides draft-copy workflow for published surveys:
- clone_survey_for_draft(): Create a draft copy of a published survey
- check_draft_compatibility(): Verify backward compatibility before publish
- publish_draft(): Atomically publish a draft copy as a new version
"""
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
    """Return the canonical survey for any version copy (or the survey itself)."""
    return survey.canonical_survey or survey


def family_ids(survey):
    """Return the set of SurveyHeader ids in the survey's version family.

    The family is the canonical survey plus its archived version copies
    (linked via the canonical_survey FK). Draft copies are linked through
    published_version instead, so they are naturally excluded — they never
    own real sessions (test sessions die with the draft at publish time).
    """
    canonical = canonical_of(survey)
    ids = {canonical.id}
    ids.update(
        SurveyHeader.objects
        .filter(canonical_survey=canonical)
        .values_list('id', flat=True)
    )
    return ids


def family_sessions(survey, include_deleted=False):
    """Sessions across the whole version family (each counted exactly once —
    a session FK-points at exactly one version header)."""
    qs = SurveySession.objects.filter(survey_id__in=family_ids(survey))
    if not include_deleted:
        qs = qs.filter(is_deleted=False)
    return qs


def lineage_map(survey):
    """Build the question-lineage map for a survey's version family.

    A lineage groups the questions that share (code, input_type) across the
    family's versions — the same logical question carried through publishes
    (clones keep codes; an input_type change intentionally breaks the lineage
    so incompatible answer shapes are never merged).

    Returns an ordered dict {(code, input_type): {
        'questions':    [Question, ...]   # newest version first
        'question_ids': [int, ...],
        'current':      Question | None,  # the canonical version's object
        'versions':     'v2' or 'v1–v3',  # display range label
    }} with current-structure lineages first (in canonical order), then
    archived-only lineages (newest first).
    """
    canonical = canonical_of(survey)
    ids = family_ids(canonical)

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
        entry['_vers'].append(header.version_number)
        if header.id == canonical.id:
            entry['current'] = q

    for entry in lineages.values():
        lo, hi = min(entry['_vers']), max(entry['_vers'])
        entry['versions'] = f'v{lo}' if lo == hi else f'v{lo}–v{hi}'
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
                # Check if any answers reference the removed codes
                affected_answers = Answer.objects.filter(
                    question=canonical_q
                ).exclude(
                    selected_choices__isnull=True
                )
                affected_count = 0
                for answer in affected_answers:
                    if answer.selected_choices and set(answer.selected_choices) & removed_codes:
                        affected_count += 1

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
