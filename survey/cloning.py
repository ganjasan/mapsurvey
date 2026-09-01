"""
Cloning primitives for SurveySection and Question.

Single source of truth for deep-cloning survey structure used by:
- versioning.clone_survey_for_draft (preserves codes; passes regenerate_code=False)
- editor_views duplicate / paste endpoints (regenerates codes; optional name suffix)

`clone_question` copies translations, sub-questions, choices, validation_settings,
and the image path reference. `clone_section` copies translations and all top-level
questions (sub-questions handled recursively by clone_question), and stitches the
new section into the target survey's linked list.
"""
from typing import Optional

from .models import (
    Question,
    QuestionTranslation,
    SurveyHeader,
    SurveySection,
    SurveySectionTranslation,
    question_code_generator,
)


def clone_question(
    question: Question,
    *,
    target_section: SurveySection,
    parent: Optional[Question] = None,
    regenerate_code: bool = True,
    name_suffix: Optional[str] = None,
    copy_sub_questions: bool = True,
) -> Question:
    """Deep-clone a question into ``target_section``.

    - ``regenerate_code=True`` (default for editor) calls ``question_code_generator()``;
      ``False`` preserves the source code (versioning use case).
    - ``name_suffix`` is appended to the new question's ``name`` if non-empty.
      Sub-questions never receive the suffix.
    - ``copy_sub_questions=False`` drops the source's sub-questions (used for the
      paste-as-sub-question flow per issue #16 Q8).
    - Translations are copied verbatim into ``QuestionTranslation`` rows for the
      new question (including all languages, regardless of the target survey's
      ``available_languages``).
    - ``image`` is copied as a path reference — the underlying file is shared.
    - ``validation_settings`` is copied (closes a bug in the legacy
      ``versioning._clone_question`` that silently dropped it).
    """
    new_code = question_code_generator() if regenerate_code else question.code
    new_name = question.name
    if name_suffix:
        new_name = f"{question.name or ''}{name_suffix}"

    # A visibility rule references a controller by code within the same survey.
    # Cloning within the survey keeps it (the controller still exists there);
    # pasting into another survey drops it — the controller does not travel.
    same_survey = target_section.survey_header_id == question.survey_section.survey_header_id
    new_question = Question.objects.create(
        survey_section=target_section,
        parent_question_id=parent,
        code=new_code,
        order_number=question.order_number,
        name=new_name,
        subtext=question.subtext,
        input_type=question.input_type,
        choices=question.choices,
        required=question.required,
        validation_settings=question.validation_settings,
        color=question.color,
        icon_class=question.icon_class,
        image=question.image,
        display_style=question.display_style,
        visibility_rule=question.visibility_rule if same_survey else None,
        # A layer belongs to one survey; pasting an Objects-on-the-map question
        # elsewhere drops the binding the way the visibility rule is dropped.
        # Draft copies and versions share the canonical survey's layers, and
        # those clone within the same survey_header lineage — see layer_owner().
        layer=question.layer if same_survey or (question.layer_id and _shares_layers(question, target_section)) else None,
        min_objects=question.min_objects,
        objects_search=question.objects_search,
    )

    for trans in QuestionTranslation.objects.filter(question=question):
        QuestionTranslation.objects.create(
            question=new_question,
            language=trans.language,
            name=trans.name,
            subtext=trans.subtext,
        )

    if copy_sub_questions:
        for sub_q in Question.objects.filter(parent_question_id=question).order_by('order_number'):
            clone_question(
                sub_q,
                target_section=target_section,
                parent=new_question,
                regenerate_code=regenerate_code,
                name_suffix=None,
                copy_sub_questions=True,
            )

    return new_question


def _shares_layers(question: Question, target_section: SurveySection) -> bool:
    """True when the source and target surveys resolve to the same layer owner
    (a draft copy or archived version of the same canonical survey)."""
    from .layers import layer_owner
    return layer_owner(question.survey_section.survey_header) == layer_owner(target_section.survey_header)


def _unique_section_name(base_name: str, target_survey: SurveyHeader) -> str:
    """Return ``base_name`` if free, else ``{base}_2``, ``{base}_3`` ..."""
    existing = set(
        SurveySection.objects.filter(survey_header=target_survey).values_list('name', flat=True)
    )
    if base_name not in existing:
        return base_name
    n = 2
    while f"{base_name}_{n}" in existing:
        n += 1
    return f"{base_name}_{n}"


def clone_section(
    section: SurveySection,
    *,
    target_survey: SurveyHeader,
    insert_after: Optional[SurveySection] = None,
    name_suffix: Optional[str] = None,
) -> SurveySection:
    """Deep-clone a section into ``target_survey``.

    Linked-list semantics:
    - ``insert_after`` set → splice the new section between ``insert_after`` and
      ``insert_after.next_section`` (3-node splice).
    - ``insert_after=None`` and target has sections → append at the tail.
    - ``insert_after=None`` and target is empty → the new section becomes head.

    Field semantics:
    - ``name`` is deduplicated within the target survey (``_2``, ``_3`` suffix).
    - ``title`` receives the optional ``name_suffix`` (e.g. ``" (copy)"``); the
      ``name`` field never receives the suffix (it must remain URL-safe).
    - ``is_head`` is reset based on the splice position; cloned section is never
      head unless inserted at the head of an empty survey.
    - All ``SurveySectionTranslation`` rows are copied verbatim.
    - All top-level questions are cloned via ``clone_question(regenerate_code=True)``.
      Sub-questions are recursively cloned by ``clone_question``.
    """
    new_name = _unique_section_name(section.name, target_survey)
    new_title = section.title
    if name_suffix and new_title:
        new_title = f"{section.title}{name_suffix}"
    elif name_suffix and not new_title:
        new_title = name_suffix.lstrip()

    is_head = (insert_after is None) and not SurveySection.objects.filter(
        survey_header=target_survey
    ).exists()

    same_survey = target_survey.id == section.survey_header_id
    new_section = SurveySection.objects.create(
        survey_header=target_survey,
        is_head=is_head,
        name=new_name,
        title=new_title,
        subheading=section.subheading,
        code=section.code,
        start_map_postion=section.start_map_postion,
        start_map_zoom=section.start_map_zoom,
        use_geolocation=section.use_geolocation,
        override_basemap=section.override_basemap,
        # A section rule's controller lives in an EARLIER section, which stays
        # behind on a cross-survey paste — so the rule only survives in-survey.
        visibility_rule=section.visibility_rule if same_survey else None,
    )

    for trans in SurveySectionTranslation.objects.filter(section=section):
        SurveySectionTranslation.objects.create(
            section=new_section,
            language=trans.language,
            title=trans.title,
            subheading=trans.subheading,
        )

    pairs = []
    code_map = {}
    for question in Question.objects.filter(
        survey_section=section, parent_question_id__isnull=True
    ).order_by('order_number'):
        clone = clone_question(
            question,
            target_section=new_section,
            parent=None,
            regenerate_code=True,
            name_suffix=None,
            copy_sub_questions=True,
        )
        pairs.append((question, clone))
        code_map[question.code] = clone.code

    # Intra-section rules must follow their cloned controller, not keep pointing
    # at the source section's question. Restored from the SOURCE rule, because
    # clone_question drops rules on cross-survey pastes — where an intra-section
    # controller travels with the section and the rule is still meaningful.
    for source_q, clone in pairs:
        rule = source_q.visibility_rule
        if isinstance(rule, dict) and rule.get('question_code') in code_map:
            clone.visibility_rule = {**rule, 'question_code': code_map[rule['question_code']]}
            clone.save(update_fields=['visibility_rule'])

    _splice_into_linked_list(new_section, target_survey, insert_after)

    return new_section


def _splice_into_linked_list(
    new_section: SurveySection,
    target_survey: SurveyHeader,
    insert_after: Optional[SurveySection],
) -> None:
    """Stitch ``new_section`` into ``target_survey``'s section linked list."""
    if insert_after is not None:
        if insert_after.survey_header_id != target_survey.pk:
            raise ValueError(
                "insert_after section belongs to a different survey than target_survey"
            )
        old_next = insert_after.next_section
        insert_after.next_section = new_section
        insert_after.save(update_fields=['next_section'])

        new_section.prev_section = insert_after
        new_section.next_section = old_next
        new_section.save(update_fields=['prev_section', 'next_section'])

        if old_next is not None:
            old_next.prev_section = new_section
            old_next.save(update_fields=['prev_section'])
        return

    tail = SurveySection.objects.filter(
        survey_header=target_survey, next_section__isnull=True
    ).exclude(pk=new_section.pk).first()
    if tail is None:
        return

    tail.next_section = new_section
    tail.save(update_fields=['next_section'])
    new_section.prev_section = tail
    new_section.save(update_fields=['prev_section'])
