"""
Survey versioning module.

Provides draft-copy workflow for published surveys:
- clone_survey_for_draft(): Create a draft copy of a published survey
- check_draft_compatibility(): Verify backward compatibility before publish
- publish_draft(): Atomically publish a draft copy as a new version
"""
from django.db import transaction
from django.db.models import Q

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


def clone_survey_for_draft(canonical):
    """
    Create a draft copy of a published survey.

    Clones sections, questions (with same codes), choices, translations,
    sub-questions, and collaborators. The draft is linked to the canonical
    via published_version FK.

    Returns the draft SurveyHeader.
    """
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
    sections = SurveySection.objects.filter(survey_header=canonical)
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
            _clone_question(question, new_section, parent=None)

    # Resolve section linked list
    for old_section in sections:
        new_section = old_to_new_section[old_section.pk]
        if old_section.next_section_id and old_section.next_section_id in old_to_new_section:
            new_section.next_section = old_to_new_section[old_section.next_section_id]
        if old_section.prev_section_id and old_section.prev_section_id in old_to_new_section:
            new_section.prev_section = old_to_new_section[old_section.prev_section_id]
        new_section.save()

    return draft


def _clone_question(question, new_section, parent):
    """Clone a question with same code, choices, translations, and sub-questions."""
    new_question = Question.objects.create(
        survey_section=new_section,
        parent_question_id=parent,
        code=question.code,
        order_number=question.order_number,
        name=question.name,
        subtext=question.subtext,
        input_type=question.input_type,
        choices=question.choices,
        required=question.required,
        color=question.color,
        icon_class=question.icon_class,
        image=question.image,
    )

    # Clone translations
    for trans in QuestionTranslation.objects.filter(question=question):
        QuestionTranslation.objects.create(
            question=new_question,
            language=trans.language,
            name=trans.name,
            subtext=trans.subtext,
        )

    # Clone sub-questions recursively
    for sub_q in Question.objects.filter(parent_question_id=question).order_by('order_number'):
        _clone_question(sub_q, new_section, parent=new_question)

    return new_question


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

        # 6. Increment version
        canonical.version_number += 1
        canonical.save()

        # 7. Delete draft (sections already moved, so just the header)
        draft.delete()

    return canonical
