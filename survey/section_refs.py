"""Section references: how a survey-level row names a section without a foreign key.

Section codes repeat within a survey (the editor's duplicate keeps the code), so a reference is
`<code>` when the code is unique in its survey and `<code>#<n>` — the n-th section of that code,
counted from 0 in id order — when it is not. The translation table keys its occurrences this way
(`section:<ref>`), and layer placements (change map-layers-study-area) name the sections a layer
is on the same way, so a draft copy, a published version and a restored one all resolve the same
reference to their own row without anything being copied.

`<code>` and `<code>#0` name the same section: a placement written while the code was unique keeps
pointing at the first section after a duplicate, never at the copy.
"""


def refs_for(header_id):
    """{section_id: ref} for every section of one survey header."""
    from .models import SurveySection
    by_code = {}
    for pk, code in (SurveySection.objects.filter(survey_header_id=header_id)
                     .order_by('id').values_list('id', 'code')):
        by_code.setdefault(code, []).append(pk)
    out = {}
    for code, ids in by_code.items():
        for index, pk in enumerate(ids):
            out[pk] = f'{code}#{index}' if len(ids) > 1 else code
    return out


def section_ref(section):
    """The reference of one section within its survey."""
    return refs_for(section.survey_header_id).get(section.pk, section.code)


def split(ref):
    """(code, index) of a reference; a bare code is index 0."""
    ref = str(ref or '')
    code, sep, index = ref.rpartition('#')
    if sep and index.isdigit():
        return code, int(index)
    return ref, 0


def matches(ref, section_ref_value):
    """Whether a stored reference names the section whose own reference is `section_ref_value`."""
    return split(ref) == split(section_ref_value)


def section_for(header_id, ref):
    """The section of a survey header a reference names, or None."""
    from .models import SurveySection
    code, index = split(ref)
    ids = list(SurveySection.objects.filter(survey_header_id=header_id, code=code)
               .order_by('id').values_list('id', flat=True))
    if index >= len(ids):
        return None
    return SurveySection.objects.filter(pk=ids[index]).first()
