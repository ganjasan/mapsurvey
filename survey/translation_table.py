"""The translation table (change translation-table, issue #454, epic #393).

One page per survey and target language lists every creator-written text once,
in respondent order, with its translation beside it. This module is the whole
mechanism underneath that page and the CSV round trip:

- **Occurrences**: one translatable field of one entity, addressed by a key
  built from entity CODES, never ids — `section:<code>[#n]:title`,
  `question:<code>:name`, `question:<code>:choice:<choice code>`,
  `group:<code>:title`, `survey:thanks`. Codes travel with the draft copy,
  publishing and restored versions, so nothing keyed by them has to be copied.
- **Rows**: occurrences grouped by identical normalised source text and kind
  (plain / rich). A group row writes one translation to every occurrence; a
  group whose occurrences carry different translations is shown split.
- **Status**: *missing* (no translation), *stale* (the source changed after
  the translation was written — `TranslationSource` keeps the hash it was
  written against), *translated*. A translation with no hash row reads as
  translated: everything written before hashes existed, ZIP imports and
  duplicates are "unknown", not "outdated".
- **One writer**: `apply()` is how the page, the CSV import and (later) the
  AI job write. It routes every value to the entity's own service path, so
  the creator-HTML coercion, length caps, the live-survey lock and the
  re-screen are the same ones the modals use.

Hashes are recorded by every translation write (`services.common.
save_translations`, `services.surveys.set_thanks`, the choices save) for the
fields whose value CHANGED, and by `apply()` for every field it saves — a
save from the table is a review. A save of the base text never touches a
hash; that is what makes "outdated" detectable.
"""
import csv
import hashlib
import io
import re
from dataclasses import dataclass, field

from django.utils.translation import gettext as _

from .html_sanitize import coerce_creator_html
from .question_types import CHOICE_TYPES
from .versioning import canonical_of

PLAIN, RICH = 'plain', 'rich'
MISSING, STALE, TRANSLATED = 'missing', 'stale', 'translated'
STATUS_ORDER = (MISSING, STALE, TRANSLATED)

# Fields with a stored length cap (the modals' caps, mirrored).
CAPS = {'section:title': 256, 'section:next_label': 30, 'question:name': 512, 'group:title': 512}

# Question types whose `name` is an editor-only label (spec question-subtext).
LABEL_ONLY_TYPES = ('html', 'image')

_WS = re.compile(r'\s+')


# ─── Keys and hashes ─────────────────────────────────────────────────────────

def normalise(text, kind):
    """The text a hash and a group key are computed over: rich text as the
    sanitizer would store it, whitespace collapsed either way."""
    text = text or ''
    if kind == RICH:
        text = coerce_creator_html(text)
    return _WS.sub(' ', str(text)).strip()


def source_hash(text, kind):
    return hashlib.sha1(normalise(text, kind).encode('utf-8')).hexdigest()


def group_key(text, kind):
    digest = hashlib.sha1((kind + '\n' + normalise(text, kind)).encode('utf-8')).hexdigest()
    return 't:' + digest[:12]


def section_prefix(section):
    """`section:<code>`, with `#n` when the survey has several sections of
    that code (they are not unique within a survey)."""
    from .models import SurveySection
    siblings = list(SurveySection.objects.filter(
        survey_header_id=section.survey_header_id, code=section.code,
    ).order_by('id').values_list('id', flat=True))
    if len(siblings) > 1:
        return f'section:{section.code}#{siblings.index(section.id)}'
    return f'section:{section.code}'


def question_prefix(question):
    return f'question:{question.code}'


def group_prefix(group):
    return f'group:{group.code}'


THANKS_KEY = 'survey:thanks'


def prefix_for(owner_field, owner):
    """The key prefix of a translation row's owner, from the `owner_field`
    `save_translations` is called with."""
    if owner_field == 'section':
        return section_prefix(owner)
    if owner_field == 'question':
        return question_prefix(owner)
    if owner_field == 'group':
        return group_prefix(owner)
    raise ValueError(owner_field)


def record_hashes(survey, language, items):
    """Upsert the hash rows of `items = [(key, source_text, kind, translated)]`
    for `language`; an item whose translation is empty loses its row."""
    from .models import TranslationSource
    canonical = canonical_of(survey)
    for key, source, kind, translated in items:
        if (translated or '').strip():
            TranslationSource.objects.update_or_create(
                survey=canonical, key=key, language=language,
                defaults={'source_hash': source_hash(source, kind)},
            )
        else:
            TranslationSource.objects.filter(survey=canonical, key=key, language=language).delete()


def hashes_for(survey, language):
    from .models import TranslationSource
    return dict(TranslationSource.objects.filter(
        survey=canonical_of(survey), language=language,
    ).values_list('key', 'source_hash'))


# ─── Occurrences ─────────────────────────────────────────────────────────────

@dataclass
class Occurrence:
    key: str
    kind: str
    source: str                 # primary-language text, as stored
    translation: str            # stored translation for the target language, '' when none
    page: int                   # 1-based page number
    page_title: str
    element: str                # "Question 1", "Option", "Thank-you page" …
    where: str                  # "Page 2 · Question 1 · option"
    entity_kind: str            # section | question | group | survey
    entity: object
    field: str                  # title | subheading | next_label | name | subtext | choice:<code> | description | thanks
    status: str = TRANSLATED
    cap: int = 0
    shown_source: str = ''      # the source column's text (another language, or the primary)
    shown_is_primary: bool = True
    link: dict = field(default_factory=dict)

    @property
    def label(self):
        return self.where


@dataclass
class Row:
    key: str
    kind: str
    source: str
    occurrences: list
    split: bool = False
    translation: str = ''       # the common translation of an unsplit row
    status: str = TRANSLATED
    shown_source: str = ''
    shown_is_primary: bool = True
    cap: int = 0

    @property
    def count(self):
        return len(self.occurrences)

    @property
    def first(self):
        return self.occurrences[0]


def _row_for(rows_by_lang, lang):
    return rows_by_lang.get(lang)


def _tr(rows_by_lang, lang, attr):
    row = rows_by_lang.get(lang)
    return (getattr(row, attr, None) or '') if row is not None else ''


def _choice_name(choice, lang):
    """The stored name of `choice` in `lang`; a flat (legacy single-language)
    name has no per-language values."""
    name = choice.get('name') if isinstance(choice, dict) else None
    if isinstance(name, dict):
        return name.get(lang) or ''
    return ''


def record_choice_hashes(survey, question, old_choices, new_choices, force=()):
    """Hashes for the per-language choice names whose value changed between
    `old_choices` and `new_choices` (plus every language/code in `force`,
    pairs of (code, lang)); the primary name is the source."""
    primary = _primary(survey)
    langs = (survey.available_languages or [])[1:]
    if not langs:
        return
    old = {c.get('code'): c for c in (old_choices or []) if isinstance(c, dict)}
    prefix = question_prefix(question)
    for choice in new_choices or []:
        if not isinstance(choice, dict):
            continue
        code = choice.get('code')
        before = old.get(code)
        for lang in langs:
            new_name = _choice_name(choice, lang)
            if (code, lang) in force or new_name != (_choice_name(before, lang) if before else ''):
                record_hashes(survey, lang, [(f'{prefix}:choice:{code}', _choice_primary(choice, primary), PLAIN, new_name)])


def _choice_primary(choice, primary):
    name = choice.get('name') if isinstance(choice, dict) else None
    if isinstance(name, dict):
        return name.get(primary) or next((v for v in name.values() if v), '') or ''
    return name or ''


def _status(occurrence, hashes):
    if not occurrence.translation.strip():
        return MISSING
    stored = hashes.get(occurrence.key)
    if stored and stored != source_hash(occurrence.source, occurrence.kind):
        return STALE
    return TRANSLATED


def _primary(survey):
    langs = list(survey.available_languages or [])
    return langs[0] if langs else 'en'


def occurrences(survey, language, source_language=None):
    """Every translatable occurrence of `survey` for the target `language`,
    in respondent order, with status. `source_language` (default the primary)
    picks what the source column shows; the primary text is the fallback."""
    from .groups import group_runs
    from .models import QuestionGroup
    from .services.sections import ordered

    primary = _primary(survey)
    source_language = source_language or primary
    hashes = hashes_for(survey, language)
    out = []

    def add(key, kind, source, translation, page, page_title, element, where,
            entity_kind, entity, fld, cap=0, shown=None, link=None):
        if not (source or '').strip():
            return
        occ = Occurrence(
            key=key, kind=kind, source=source, translation=translation or '',
            page=page, page_title=page_title, element=element, where=where,
            entity_kind=entity_kind, entity=entity, field=fld, cap=cap, link=link or {},
        )
        occ.status = _status(occ, hashes)
        if shown is not None and source_language != primary and shown.strip():
            occ.shown_source, occ.shown_is_primary = shown, False
        else:
            occ.shown_source, occ.shown_is_primary = source, True
        out.append(occ)

    sections = ordered(survey)
    groups = {}
    for group in QuestionGroup.objects.filter(
        survey_section__survey_header=survey,
    ).prefetch_related('translations').order_by('order_number'):
        groups.setdefault((group.survey_section_id, group.parent_question_id), []).append(group)

    for page, section in enumerate(sections, start=1):
        title = section.title or section.name or ''
        page_title = _('Page %(n)s: %(title)s') % {'n': page, 'title': title}
        where_page = _('Page %(n)s') % {'n': page}
        tr = {t.language: t for t in section.translations.all()}
        prefix = section_prefix(section)
        link = {'section_id': section.id}
        add(f'{prefix}:title', PLAIN, section.title, _tr(tr, language, 'title'),
            page, page_title, _('Page title'), f'{where_page} · {_("Page title")}',
            'section', section, 'title', CAPS['section:title'],
            shown=_tr(tr, source_language, 'title'), link=link)
        add(f'{prefix}:subheading', RICH, section.subheading, _tr(tr, language, 'subheading'),
            page, page_title, _('Page intro'), f'{where_page} · {_("Page intro")}',
            'section', section, 'subheading', shown=_tr(tr, source_language, 'subheading'), link=link)
        add(f'{prefix}:next_label', PLAIN, section.next_label, _tr(tr, language, 'next_label'),
            page, page_title, _('Next button'), f'{where_page} · {_("Next button")}',
            'section', section, 'next_label', CAPS['section:next_label'],
            shown=_tr(tr, source_language, 'next_label'), link=link)

        number = 0

        def add_group(group, where_prefix):
            gtr = {t.language: t for t in group.translations.all()}
            gprefix = group_prefix(group)
            glabel = _('Group: %(title)s') % {'title': group.title or _('(untitled)')}
            glink = {'section_id': section.id, 'group_id': group.id}
            add(f'{gprefix}:title', PLAIN, group.title, _tr(gtr, language, 'title'),
                page, page_title, _('Group title'), f'{where_prefix} · {glabel}',
                'group', group, 'title', CAPS['group:title'],
                shown=_tr(gtr, source_language, 'title'), link=glink)
            add(f'{gprefix}:description', RICH, group.description, _tr(gtr, language, 'description'),
                page, page_title, _('Group description'), f'{where_prefix} · {glabel} · {_("description")}',
                'group', group, 'description', shown=_tr(gtr, source_language, 'description'), link=glink)

        def add_question(question, where_prefix, element):
            qtr = {t.language: t for t in question.translations.all()}
            qprefix = question_prefix(question)
            qlink = {'section_id': section.id, 'question_id': question.id}
            if question.input_type not in LABEL_ONLY_TYPES:
                add(f'{qprefix}:name', PLAIN, question.name, _tr(qtr, language, 'name'),
                    page, page_title, element, f'{where_prefix} · {element}',
                    'question', question, 'name', CAPS['question:name'],
                    shown=_tr(qtr, source_language, 'name'), link=qlink)
            sub_element = _('Formatted text') if question.input_type == 'html' else _('%(q)s help text') % {'q': element}
            add(f'{qprefix}:subtext', RICH, question.subtext, _tr(qtr, language, 'subtext'),
                page, page_title, sub_element, f'{where_prefix} · {sub_element}',
                'question', question, 'subtext', shown=_tr(qtr, source_language, 'subtext'), link=qlink)
            if question.input_type in CHOICE_TYPES and question.input_type != 'thumbs':
                for choice in question.choices or []:
                    if not isinstance(choice, dict):
                        continue
                    opt = _('%(q)s option') % {'q': element}
                    add(f'{qprefix}:choice:{choice.get("code")}', PLAIN,
                        _choice_primary(choice, primary), _choice_name(choice, language),
                        page, page_title, opt, f'{where_prefix} · {opt}',
                        'question', question, f'choice:{choice.get("code")}',
                        shown=_choice_name(choice, source_language), link=qlink)

        for group, questions in group_runs(list(section.questions()), groups.get((section.id, None), [])):
            if group is not None:
                add_group(group, where_page)
            for question in questions:
                if question.input_type in LABEL_ONLY_TYPES:
                    element = _('Formatted text') if question.input_type == 'html' else _('Image')
                else:
                    number += 1
                    element = _('Question %(n)s') % {'n': number}
                add_question(question, where_page, element)
                sub_number = 0
                for sgroup, subs in group_runs(list(question.subQuestions()), groups.get((section.id, question.id), [])):
                    if sgroup is not None:
                        add_group(sgroup, f'{where_page} · {element}')
                    for sub in subs:
                        sub_number += 1
                        add_question(sub, f'{where_page} · {element}',
                                     _('Sub-question %(n)s') % {'n': sub_number})

    thanks = survey.thanks_html or {}
    if isinstance(thanks, str):
        thanks = {primary: thanks}
    add(THANKS_KEY, RICH, thanks.get(primary, ''), thanks.get(language, ''),
        len(sections) + 1, _('Thank-you page'), _('Thank-you page'), _('Thank-you page'),
        'survey', survey, 'thanks', shown=thanks.get(source_language, ''), link={'panel': 'thanks'})
    return out


def rows_for(occs, split_keys=()):
    """Group occurrences into table rows. A group whose occurrences carry
    different non-empty translations is split; `split_keys` splits more."""
    rows, index = [], {}
    for occ in occs:
        key = group_key(occ.source, occ.kind)
        row = index.get(key)
        if row is None:
            row = Row(key=key, kind=occ.kind, source=occ.source, occurrences=[],
                      shown_source=occ.shown_source, shown_is_primary=occ.shown_is_primary, cap=occ.cap)
            index[key] = row
            rows.append(row)
        row.occurrences.append(occ)
    for row in rows:
        values = {o.translation.strip() for o in row.occurrences if o.translation.strip()}
        row.split = len(values) > 1 or row.key in split_keys
        row.translation = next(iter(values)) if len(values) == 1 else ''
        row.status = min((o.status for o in row.occurrences), key=STATUS_ORDER.index)
    return rows


def counts(rows):
    out = {MISSING: 0, STALE: 0, TRANSLATED: 0}
    for row in rows:
        out[row.status] += 1
    return out


def outdated_by_entity(survey):
    """{(entity_kind, entity id): [lang, …]} of entities with a stale
    translation, for the gap engine."""
    out = {}
    for lang in (survey.available_languages or [])[1:]:
        for occ in occurrences(survey, lang):
            if occ.status == STALE:
                langs = out.setdefault((occ.entity_kind, occ.entity.id), [])
                if lang not in langs:
                    langs.append(lang)
    return out


# ─── The writer ──────────────────────────────────────────────────────────────

@dataclass
class Report:
    filled: int = 0
    overwritten: int = 0
    skipped: int = 0
    cleared: int = 0
    unmatched: list = field(default_factory=list)

    @property
    def written(self):
        return self.filled + self.overwritten + self.cleared


def apply(actor, survey, language, values, *, overwrite=False, clear_empty=False):
    """Write `values = {key: text}` (group or occurrence keys) for `language`.

    An occurrence that already has a translation is left alone unless
    `overwrite`; an empty value clears the translation only with
    `clear_empty` (the table), never from a CSV. Every write goes through
    the entity's service path and records the source hash.
    """
    from . import product_events as pe
    from .services import locks
    from .services.common import surface_props
    from .services.groups import save_translations_for as save_group
    from .services.questions import save_translations_for as save_question, set_choice_names
    from .services.sections import save_translations_for as save_section
    from .services.surveys import set_thanks

    if language not in (survey.available_languages or [])[1:]:
        raise ValueError(language)
    locks.assert_content_editable(survey)
    report = Report()
    occs = occurrences(survey, language)
    by_occurrence = {o.key: o for o in occs}
    by_group = {}
    for occ in occs:
        by_group.setdefault(group_key(occ.source, occ.kind), []).append(occ)

    planned = {}   # occurrence key -> (occurrence, text)
    for key, text in values.items():
        targets = by_group.get(key) or ([by_occurrence[key]] if key in by_occurrence else None)
        if targets is None:
            report.unmatched.append(key)
            continue
        text = (text or '').strip()
        for occ in targets:
            existing = occ.translation.strip()
            if not text:
                if clear_empty and existing:
                    planned[occ.key] = (occ, '')
                    report.cleared += 1
                continue
            if existing and not overwrite and existing != text:
                report.skipped += 1
                continue
            if existing and existing != text:
                report.overwritten += 1
            elif not existing:
                report.filled += 1
            planned[occ.key] = (occ, text)

    # Group the writes per entity so each service call carries the full
    # field set (save_translations blanks what it is not given).
    per_entity = {}
    for occ, text in planned.values():
        per_entity.setdefault((occ.entity_kind, occ.entity.id), (occ.entity, {}))[1][occ.field] = text

    for (kind, _id), (entity, fields) in per_entity.items():
        if kind == 'section':
            _write_rows(save_section, entity, survey, language, fields, ('title', 'subheading', 'next_label'))
        elif kind == 'group':
            _write_rows(save_group, entity, survey, language, fields, ('title', 'description'))
        elif kind == 'question':
            names = {f.split(':', 1)[1]: v for f, v in fields.items() if f.startswith('choice:')}
            plain = {f: v for f, v in fields.items() if not f.startswith('choice:')}
            if plain:
                _write_rows(save_question, entity, survey, language, plain, ('name', 'subtext'))
            if names:
                set_choice_names(entity, language, names)
        elif kind == 'survey':
            set_thanks(actor, survey, {language: fields.get('thanks', '')}, languages=[language])
            thanks = survey.thanks_html if isinstance(survey.thanks_html, dict) else {}
            record_hashes(survey, language, [(THANKS_KEY, thanks.get(_primary(survey), ''), RICH, fields.get('thanks', ''))])

    if planned and locks.locks(survey)[1]:
        pe.emit(pe.LIVE_EDIT_SAVED, actor.user_id,
                {'survey_id': str(survey.id), 'kind': 'translation', **surface_props(actor)})
        locks.rescreen_if_live(survey)
    return report


def _write_rows(save, entity, survey, language, new_values, all_fields):
    """One `save_translations_for` call with the full field set: the fields
    not being written keep their stored value."""
    row = next((t for t in entity.translations.all() if t.language == language), None)
    merged = {f: (new_values[f] if f in new_values else (getattr(row, f, None) or '')) for f in all_fields}
    save(entity, survey, {language: merged}, record_all=tuple(new_values))


# ─── CSV ─────────────────────────────────────────────────────────────────────

CSV_COLUMNS = ('key', 'page', 'element', 'source', 'translation', 'status')
_FORMULA = ('=', '+', '-', '@')
_BLOCK_TAGS = re.compile(r'</(p|div|h[1-6]|li|blockquote|pre)>|<br\s*/?>', re.I)
_TAGS = re.compile(r'<[^>]+>')


def rich_to_text(html):
    """Rich text as a translator reads it in a spreadsheet: blocks separated
    by a blank line, tags gone. Inline markup does not survive — the page says so."""
    text = _BLOCK_TAGS.sub('\n\n', html or '')
    text = _TAGS.sub('', text)
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def text_to_rich(text):
    """Plain paragraphs back into `<p>`s; text that already carries markup is
    left for the sanitizer."""
    text = (text or '').strip()
    if not text or '<' in text and '>' in text:
        return text
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    from django.utils.html import escape
    return ''.join('<p>%s</p>' % escape(p).replace('\n', '<br>') for p in paragraphs)


def _cell(value):
    value = value if value is not None else ''
    return "'" + value if value[:1] in _FORMULA else value


def _uncell(value):
    value = (value or '').strip()
    return value[1:] if value[:1] == "'" and value[1:2] in _FORMULA else value


def export_csv(rows):
    """UTF-8 with a BOM, one line per table row (one per occurrence for a split row)."""
    out = io.StringIO()
    out.write('﻿')
    writer = csv.writer(out, lineterminator='\n')
    writer.writerow(CSV_COLUMNS)
    for row in rows:
        if row.split:
            for occ in row.occurrences:
                writer.writerow(_line(occ.key, occ, occ.translation, occ.status))
        else:
            first = row.first
            element = first.element if row.count == 1 else '%s (×%d)' % (first.element, row.count)
            writer.writerow(_line(row.key, first, row.translation, row.status, element))
    return out.getvalue()


def _line(key, occ, translation, status, element=None):
    source = rich_to_text(occ.source) if occ.kind == RICH else occ.source
    translation = rich_to_text(translation) if occ.kind == RICH else translation
    return [key, _cell(occ.page_title), _cell(element or occ.element), _cell(source), _cell(translation), status]


def parse_csv(data):
    """Rows of an uploaded CSV as dicts with lower-cased, stripped headers.
    Accepts `;` and tab delimiters and a byte-order mark."""
    text = data.decode('utf-8-sig', errors='replace') if isinstance(data, bytes) else data
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=',;\t')
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    rows = []
    for raw in reader:
        rows.append({(k or '').strip().lower(): (v or '') for k, v in raw.items()})
    return rows


def values_from_csv(parsed, rows):
    """`({key: text}, unmatched)` from parsed CSV rows: matched by `key`, then by
    the exact normalised `source` text (a hand-built file in the export's shape).
    Rich values typed as plain text get their paragraphs back."""
    by_key, by_source = {}, {}
    for row in rows:
        by_key[row.key] = (row.key, row.kind)
        by_source.setdefault(normalise(row.source, row.kind), (row.key, row.kind))
        for occ in row.occurrences:
            by_key[occ.key] = (occ.key, occ.kind)
    values, unmatched = {}, []
    for line in parsed:
        key = (line.get('key') or '').strip()
        source = _uncell(line.get('source'))
        translation = _uncell(line.get('translation'))
        match = by_key.get(key)
        if match is None:
            match = by_source.get(normalise(source, PLAIN)) or by_source.get(normalise(source, RICH))
        if match is None:
            unmatched.append(source or key)
            continue
        key, kind = match
        if not translation:
            continue
        values[key] = text_to_rich(translation) if kind == RICH else translation
    return values, unmatched
