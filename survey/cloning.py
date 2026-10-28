"""
Cloning primitives for SurveySection and Question.

Single source of truth for deep-cloning survey structure used by:
- versioning.clone_survey_for_draft (preserves codes; passes regenerate_code=False)
- editor_views duplicate / paste endpoints (regenerates codes; optional name suffix)

`clone_question` copies translations, sub-questions, choices, validation_settings,
and the image: as a path reference within one survey family, as a new stored file
across surveys (`copy_file`), because purging a survey deletes its files. `clone_section` copies translations and all top-level
questions (sub-questions handled recursively by clone_question), and stitches the
new section into the target survey's linked list.

Plain fields are taken from the model's field list (`plain_field_values`), never from a
hand-written list: #329 was a draft copy that silently dropped `layout`, `next_label`,
`hidden_layers` and both visibility rules because the list in versioning.py predated
them. Only the fields a copy has to DECIDE about (`code`, `name`, `title`, `is_head`,
`visibility_rule`, the relations) are named explicitly, so a new column is copied on day
one and a column that must NOT travel is an explicit exclusion, not an omission.
"""
import copy
import logging
import os
from typing import Iterable, Optional

from django.core.files.base import File
from django.db.models import FileField

from .models import (
    Question,
    QuestionGroup,
    QuestionGroupTranslation,
    QuestionTranslation,
    SurveyHeader,
    SurveySection,
    SurveySectionTranslation,
    group_code_generator,
    question_code_generator,
)

logger = logging.getLogger(__name__)

# Fields every section copy decides about itself; everything else plain is copied.
SECTION_DECIDED_FIELDS = ('is_head', 'name', 'title', 'visibility_rule')
# Same for questions. Relations (section, parent, layer, group) are never plain.
QUESTION_DECIDED_FIELDS = ('code', 'name', 'visibility_rule')
# Same for question groups (change question-groups); section and parent are relations.
GROUP_DECIDED_FIELDS = ('code', 'visibility_rule')


def plain_field_values(instance, exclude: Iterable[str] = ()) -> dict:
    """``{attname: value}`` for every concrete, non-relational, non-primary-key field of
    ``instance`` except ``exclude`` — the kwargs a copy needs beyond what it decides.

    JSON values are deep-copied so the copy never aliases the source row's list/dict
    in memory. File fields copy the path reference (the file itself is shared)."""
    excluded = set(exclude)
    values = {}
    for field in instance._meta.concrete_fields:
        if field.primary_key or field.is_relation or field.name in excluded:
            continue
        value = getattr(instance, field.attname)
        if isinstance(value, (list, dict)):
            value = copy.deepcopy(value)
        elif isinstance(field, FileField):
            # The name, not the source's FieldFile: Django rebinds a FieldFile
            # object to whichever instance it is assigned to, so sharing it
            # would let a copy's new file name change the source in memory.
            value = value.name if value else ''
        values[field.attname] = value
    return values


def copy_file(field_file, instance, created=None):
    """A new stored copy of `field_file` under a fresh key from the field's own
    `upload_to` for `instance`; returns the new name, or '' when the source is
    empty or missing from storage (logged, the copy goes on without it).

    Cross-survey copies own their files (change api-v2-structure): `trash.purge`
    deletes a purged survey's cover, question images and layer assets, so a
    shared name would vanish from the other survey too. `created` collects the
    new names so a failed copy can delete them."""
    if not field_file:
        return ''
    storage = field_file.storage
    try:
        with storage.open(field_file.name, 'rb') as source:
            target = field_file.field.generate_filename(instance, os.path.basename(field_file.name))
            name = storage.save(target, File(source))
    except Exception:  # noqa: BLE001 — a lost object must not stop the copy
        logger.warning('copy_file: could not copy %s', field_file.name, exc_info=True)
        return ''
    if created is not None:
        created.append((storage, name))
    return name


def copy_section(
    section: SurveySection,
    *,
    target_survey: SurveyHeader,
    is_head: bool,
    name: Optional[str] = None,
    title: Optional[str] = None,
    keep_rule: bool,
    created_files=None,
) -> SurveySection:
    """Create a copy of ``section`` (with all its translations) in ``target_survey``.

    The linked list (``next_section``/``prev_section``) is the caller's business.
    ``keep_rule`` says whether the section's visibility rule travels: it names a
    controller in an EARLIER section, which exists in the target only when the whole
    survey is copied (draft / version restore) or the copy stays in-survey."""
    new_section = SurveySection.objects.create(
        survey_header=target_survey,
        is_head=is_head,
        name=section.name if name is None else name,
        title=section.title if title is None else title,
        visibility_rule=copy.deepcopy(section.visibility_rule) if keep_rule else None,
        **plain_field_values(section, exclude=SECTION_DECIDED_FIELDS),
    )
    # The stage picture is shared within one survey family, a new file across
    # surveys -- the same rule as Question.image (change section-layout-controls).
    if section.stage_image:
        from .layers import layer_owner
        if layer_owner(section.survey_header) != layer_owner(target_survey):
            new_section.stage_image.name = copy_file(section.stage_image, new_section, created_files)
            new_section.save(update_fields=['stage_image'])
    for trans in SurveySectionTranslation.objects.filter(section=section):
        SurveySectionTranslation.objects.create(
            section=new_section, **plain_field_values(trans),
        )
    return new_section


def clone_groups(source_section, target_section, source_parent, target_parent, *,
                 regenerate_code, keep_rule):
    """Copy the groups of one bucket (a section's top level, or one pop-up) with
    their translations; returns {source group id: new group}. Members are attached
    by `attach_group_members` once they exist (change question-groups)."""
    groups = QuestionGroup.objects.filter(survey_section=source_section)
    groups = groups.filter(parent_question__isnull=True) if source_parent is None \
        else groups.filter(parent_question=source_parent)
    mapping = {}
    for group in groups.order_by('order_number', 'id'):
        new_group = QuestionGroup.objects.create(
            survey_section=target_section,
            parent_question=target_parent,
            code=group_code_generator() if regenerate_code else group.code,
            visibility_rule=copy.deepcopy(group.visibility_rule) if keep_rule else None,
            **plain_field_values(group, exclude=GROUP_DECIDED_FIELDS),
        )
        for trans in QuestionGroupTranslation.objects.filter(group=group):
            QuestionGroupTranslation.objects.create(group=new_group, **plain_field_values(trans))
        mapping[group.id] = new_group
    return mapping


def attach_group_members(pairs, group_map, code_map=None):
    """Point every cloned question at the clone of its source's group, and — when
    codes were regenerated — a group rule naming a cloned controller at the clone
    (the remap clone_section does for question rules)."""
    for source, clone in pairs:
        if source.group_id in group_map:
            clone.group = group_map[source.group_id]
            clone.save(update_fields=['group'])
    if code_map:
        for source_id, new_group in group_map.items():
            rule = QuestionGroup.objects.get(pk=source_id).visibility_rule
            if isinstance(rule, dict) and rule.get('question_code') in code_map:
                new_group.visibility_rule = {**rule, 'question_code': code_map[rule['question_code']]}
                new_group.save(update_fields=['visibility_rule'])


def clone_top_level_questions(section, new_section, *, regenerate_code, keep_group_rules,
                              created_files=None):
    """Clone a section's top-level groups and questions (sub-questions and pop-up
    groups recursively through clone_question). Returns (pairs, code_map)."""
    group_map = clone_groups(section, new_section, None, None,
                             regenerate_code=regenerate_code, keep_rule=keep_group_rules)
    pairs = []
    code_map = {}
    for question in Question.objects.filter(
        survey_section=section, parent_question_id__isnull=True
    ).order_by('order_number'):
        clone = clone_question(
            question,
            target_section=new_section,
            parent=None,
            regenerate_code=regenerate_code,
            name_suffix=None,
            copy_sub_questions=True,
            created_files=created_files,
        )
        pairs.append((question, clone))
        code_map[question.code] = clone.code
    attach_group_members(pairs, group_map, code_map if regenerate_code else None)
    return pairs, code_map


def clone_question(
    question: Question,
    *,
    target_section: SurveySection,
    parent: Optional[Question] = None,
    regenerate_code: bool = True,
    name_suffix: Optional[str] = None,
    copy_sub_questions: bool = True,
    created_files: Optional[list] = None,
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
    - ``image`` is shared within one survey family and copied to a new file across
      surveys (``copy_file``).
    - ``validation_settings`` is copied (closes a bug in the legacy
      ``versioning._clone_question`` that silently dropped it).
    """
    new_code = question_code_generator() if regenerate_code else question.code
    new_name = question.name
    if name_suffix:
        new_name = f"{question.name or ''}{name_suffix}"

    # A visibility rule names its controller by code. It survives when the controller
    # still resolves in the target: a copy within the same survey, or a copy that keeps
    # codes (the draft / version-restore path copies the whole survey, #329). A
    # cross-survey paste regenerates codes and leaves the controller behind, so the
    # rule is dropped.
    same_survey = target_section.survey_header_id == question.survey_section.survey_header_id
    keep_rule = same_survey or not regenerate_code
    same_family = same_survey or _shares_layers(question, target_section)
    new_question = Question.objects.create(
        survey_section=target_section,
        parent_question_id=parent,
        code=new_code,
        name=new_name,
        visibility_rule=copy.deepcopy(question.visibility_rule) if keep_rule else None,
        # A layer belongs to one survey; pasting an Objects-on-the-map question
        # elsewhere drops the binding the way the visibility rule is dropped.
        # Draft copies and versions share the canonical survey's layers, and
        # those clone within the same survey_header lineage — see layer_owner().
        layer=question.layer if question.layer_id and same_family else None,
        **plain_field_values(question, exclude=QUESTION_DECIDED_FIELDS),
    )
    if question.image and not same_family:
        new_question.image.name = copy_file(question.image, new_question, created_files)
        new_question.save(update_fields=['image'])

    for trans in QuestionTranslation.objects.filter(question=question):
        QuestionTranslation.objects.create(
            question=new_question, **plain_field_values(trans),
        )

    if copy_sub_questions:
        # Pop-up groups travel with their parent on every path, rules included:
        # their controllers are siblings that travel too (change question-groups).
        group_map = clone_groups(question.survey_section, target_section, question, new_question,
                                 regenerate_code=regenerate_code, keep_rule=True)
        sub_pairs = []
        for sub_q in Question.objects.filter(parent_question_id=question).order_by('order_number'):
            sub_pairs.append((sub_q, clone_question(
                sub_q,
                target_section=target_section,
                parent=new_question,
                regenerate_code=regenerate_code,
                name_suffix=None,
                copy_sub_questions=True,
                created_files=created_files,
            )))
        # A pop-up rule names a SIBLING by code (#338). The siblings travel with
        # the parent on every path, including a cross-survey paste, so the rule
        # always survives — pointed at the cloned sibling when codes were
        # regenerated (the same remap copy_section does for intra-section rules).
        sub_code_map = {src.code: clone.code for src, clone in sub_pairs}
        if regenerate_code:
            for src, clone in sub_pairs:
                rule = src.visibility_rule
                if isinstance(rule, dict) and rule.get('question_code') in sub_code_map:
                    clone.visibility_rule = {**rule, 'question_code': sub_code_map[rule['question_code']]}
                    clone.save(update_fields=['visibility_rule'])
        attach_group_members(sub_pairs, group_map, sub_code_map if regenerate_code else None)

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
    created_files: Optional[list] = None,
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

    # A section rule's controller lives in an EARLIER section, which stays behind
    # on a cross-survey paste — so the rule only survives in-survey.
    new_section = copy_section(
        section,
        target_survey=target_survey,
        is_head=is_head,
        name=new_name,
        title=new_title,
        keep_rule=target_survey.id == section.survey_header_id,
    )

    # Group rules: kept in-survey, then remapped to cloned intra-section
    # controllers (restored from the source rule even across surveys, like the
    # question rules below).
    pairs, code_map = clone_top_level_questions(
        section, new_section, regenerate_code=True,
        keep_group_rules=target_survey.id == section.survey_header_id,
        created_files=created_files)

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


# ─── Whole-survey copy (change api-v2-structure) ────────────────────────────

# Header fields a copy decides itself or must not carry: identity, lifecycle,
# version family, trash state and the cover (copied as a new file). Everything
# else -- settings, languages, thanks page, map start, branding, embed hosts,
# password -- travels, so a copy behaves like its source. A new column is
# copied on day one; one that must not travel is added here
# (DuplicateSurveyKeepsFieldsTest fails otherwise).
SURVEY_COPY_EXCLUDED_FIELDS = (
    'uuid', 'test_token', 'name', 'status', 'cover_image', 'is_archived',
    'created_at', 'updated_at', 'deleted_at', 'version_number', 'is_canonical',
)
# Layer columns rebuilt from the copied objects (`rebuild_layer`).
LAYER_DERIVED_FIELDS = ('geojson_gz', 'geojson_legacy', 'feature_count', 'size_bytes',
                        'property_names', 'updated_at')
OBJECT_COPY_EXCLUDED_FIELDS = ('created_at', 'updated_at')
ASSET_COPY_EXCLUDED_FIELDS = ('file', 'created_at')
COPY_SUFFIX = ' (copy)'


def copy_name(name, limit=45):
    """`<name> (copy)` within the column's length."""
    return f"{(name or '')[:limit - len(COPY_SUFFIX)].rstrip()}{COPY_SUFFIX}"


def asset_bytes(survey):
    """Stored bytes of the layer attachments a copy of `survey` would duplicate."""
    from django.db.models import Sum
    from .layers import layer_owner
    from .models import LayerObjectAsset
    return LayerObjectAsset.objects.filter(
        object__layer__survey=layer_owner(survey), object__layer__source='upload',
    ).exclude(file='').aggregate(total=Sum('size_bytes'))['total'] or 0


def clone_layers(source_owner, target, created_files=None):
    """Copy the layers of `source_owner` onto `target`: creator layers with
    their objects and attachments, shared-map layers with their settings only
    (their objects are other respondents' answers). Returns {old id: new layer}."""
    from .layers import GEOMETRY_TEXT_FIELDS, rebuild_layer
    from .models import LayerObject, LayerObjectAsset, SurveyMapLayer
    mapping = {}
    for layer in SurveyMapLayer.objects.filter(survey=source_owner).defer(
            *GEOMETRY_TEXT_FIELDS).order_by('position', 'id'):
        new_layer = SurveyMapLayer.objects.create(
            survey=target, **plain_field_values(layer, exclude=LAYER_DERIVED_FIELDS))
        if layer.source != 'question':
            for obj in LayerObject.objects.filter(layer=layer).order_by('position', 'id'):
                new_obj = LayerObject.objects.create(
                    layer=new_layer, **plain_field_values(obj, exclude=OBJECT_COPY_EXCLUDED_FIELDS))
                for asset in LayerObjectAsset.objects.filter(object=obj).order_by('position', 'id'):
                    new_asset = LayerObjectAsset(
                        object=new_obj, **plain_field_values(asset, exclude=ASSET_COPY_EXCLUDED_FIELDS))
                    if asset.file:
                        new_asset.file.name = copy_file(asset.file, new_asset, created_files)
                    new_asset.save()
        rebuild_layer(new_layer)
        mapping[layer.pk] = new_layer
    return mapping


def clone_survey(source, *, created_by, created_files=None):
    """A new, independent draft survey with `source`'s structure and copies of
    its layers.

    `source` is the canonical survey or its unpublished changes: the structure
    comes from that row, the header settings and the name from the canonical
    survey (a draft copy's header mirrors it; its name is "[draft] ..."), the
    layers from the canonical owner. Codes are kept, so every visibility rule
    keeps resolving with nothing to remap; layer bindings are pointed at the
    copied layers. Nothing about respondents, versions, links, collaborators,
    comments or the public results page is copied -- the caller adds the owner.
    """
    from .layers import layer_owner
    canonical = source.published_version or source
    survey = SurveyHeader.objects.create(
        organization=canonical.organization,
        created_by=created_by,
        name=copy_name(canonical.name),
        status='draft',
        **plain_field_values(canonical, exclude=SURVEY_COPY_EXCLUDED_FIELDS),
    )
    if canonical.cover_image:
        survey.cover_image.name = copy_file(canonical.cover_image, survey, created_files)
        survey.save(update_fields=['cover_image'])

    sections = list(SurveySection.objects.filter(survey_header=source))
    new_by_old = {}
    for section in sections:
        new_section = copy_section(section, target_survey=survey, is_head=section.is_head, keep_rule=True,
                                   created_files=created_files)
        new_by_old[section.pk] = new_section
        clone_top_level_questions(section, new_section, regenerate_code=False, keep_group_rules=True,
                                  created_files=created_files)
    for section in sections:
        new_section = new_by_old[section.pk]
        new_section.next_section = new_by_old.get(section.next_section_id)
        new_section.prev_section = new_by_old.get(section.prev_section_id)
        new_section.save(update_fields=['next_section', 'prev_section'])

    layer_map = clone_layers(layer_owner(source), survey, created_files)
    for code, layer_id in Question.objects.filter(
            survey_section__survey_header=source, layer_id__isnull=False).values_list('code', 'layer_id'):
        if layer_id in layer_map:
            Question.objects.filter(survey_section__survey_header=survey, code=code).update(
                layer=layer_map[layer_id])
    return survey
