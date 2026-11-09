"""Translations of a site (change site-translations, #618; Sites v1.1 wave B).

The survey translation table (`translation_table.py`) generalised to a site: the same
`Occurrence`/`Row` records, grouping of identical text, statuses, CSV round trip and the same
page script, over a site's own fields. Differences from surveys, on purpose:

- **Keys carry ids, not codes**: `site:title`, `block:<pk>:<field>`. A site has no draft copy
  and no versions — blocks are edited in place — so a block id is stable for its whole life,
  and a duplicated site copies its translations with its blocks.
- **Storage is JSON on the rows**: `Site.translations[lang][field]`,
  `SiteBlock.translations[lang][field]` (file titles as `file:<pk>`), and the source hashes in
  `Site.translation_sources[lang][key]` — no shared table is touched.
- **Row fields are indexed** (`faq:2:q`, `phase:0:when`, `person:1:role`): moving a FAQ row
  moves its translation with the index, and the source hash then calls it outdated.

The one writer is `services.sites.set_translations`; `apply()` routes the page, the CSV import
and (later) an AI job to it.
"""
import copy

from django.utils.translation import gettext as _

from . import sites
from . import translation_table as tt
from .translation_table import PLAIN, RICH

SITE_FIELDS = (('title', PLAIN, 120), ('summary', PLAIN, 300), ('cover_alt', PLAIN, 200))

# Plain/rich fields read straight from block.data, per kind; rows are handled below.
DATA_FIELDS = {
    'text': (('body', RICH, 0),),
    'image': (('alt', PLAIN, 200), ('caption', PLAIN, 300)),
    'video': (('caption', PLAIN, 300),),
    'map': (('caption', PLAIN, 300),),
    'button': (('label', PLAIN, 60),),
    'survey': (('description', PLAIN, 300), ('button_label', PLAIN, 40)),
    'event': (('place', PLAIN, 200), ('description', PLAIN, 300)),
    'contacts': (('address', PLAIN, 300), ('hours', PLAIN, 200)),
    'compare': (('before_label', PLAIN, 40), ('after_label', PLAIN, 40)),
}
ROW_FIELDS = {
    'faq': ('items', 'faq', (('q', PLAIN, 200), ('a', RICH, 0))),
    'timeline': ('items', 'phase', (('title', PLAIN, 120), ('when', PLAIN, 60), ('body', PLAIN, 600))),
    'contacts': ('people', 'person', (('role', PLAIN, 120),)),
}


def languages(site):
    """[primary, *others] — the primary is the site's own language."""
    return [site.language] + [code for code in (site.languages or []) if code != site.language]


def block_fields(block):
    """[(field, kind, cap, source text)] of one block, in the order the page shows them."""
    data = block.data if isinstance(block.data, dict) else {}
    out = [('title', PLAIN, 120, block.title or '')]
    for name, kind, cap in DATA_FIELDS.get(block.kind, ()):
        out.append((name, kind, cap, data.get(name) or ''))
    if block.kind in ROW_FIELDS:
        key, prefix, fields = ROW_FIELDS[block.kind]
        for i, item in enumerate(data.get(key) or []):
            if not isinstance(item, dict):
                continue
            for name, kind, cap in fields:
                out.append((f'{prefix}:{i}:{name}', kind, cap, item.get(name) or ''))
    if block.kind in ('documents', 'gallery'):
        for f in block.files.all():
            out.append((f'file:{f.pk}', PLAIN, 200, f.title or ''))
    return out


def field_spec(block, field):
    """(kind, cap) of a block field, or None when the block has no such field now."""
    for name, kind, cap, _source in block_fields(block):
        if name == field:
            return kind, cap
    return None


def _label(field):
    names = {'title': _('Heading'), 'body': _('Text'), 'alt': _('Picture description'), 'caption': _('Caption'),
             'label': _('Button label'), 'description': _('Description'), 'button_label': _('Button label'),
             'place': _('Place'), 'address': _('Address'), 'hours': _('Opening hours'),
             'summary': _('Summary'), 'cover_alt': _('Cover picture description')}
    if field in names:
        return names[field]
    parts = field.split(':')
    if parts[0] == 'faq':
        return (_('Question %(n)s') if parts[2] == 'q' else _('Answer %(n)s')) % {'n': int(parts[1]) + 1}
    if parts[0] == 'phase':
        return _('Phase %(n)s') % {'n': int(parts[1]) + 1}
    if parts[0] == 'person':
        return _('Person %(n)s role') % {'n': int(parts[1]) + 1}
    if parts[0] == 'file':
        return _('File title')
    if field in ('before_label', 'after_label'):
        return _('Before label') if field == 'before_label' else _('After label')
    return field


def occurrences(site, language, source_language=None):
    """Every translatable occurrence of `site` for the target `language`, in page order."""
    primary = site.language
    source_language = source_language or primary
    hashes = (site.translation_sources or {}).get(language, {})
    out = []

    def add(key, kind, source, translation, page, page_title, element, entity_kind, entity, fld, cap,
            shown, link):
        if not (source or '').strip():
            return
        occ = tt.Occurrence(key=key, kind=kind, source=source, translation=translation or '', page=page,
                            page_title=page_title, element=element, where=f'{page_title} · {element}',
                            entity_kind=entity_kind, entity=entity, field=fld, cap=cap, link=link)
        occ.status = tt._status(occ, hashes)
        if source_language != primary and (shown or '').strip():
            occ.shown_source, occ.shown_is_primary = shown, False
        else:
            occ.shown_source, occ.shown_is_primary = source, True
        out.append(occ)

    site_tr = site.translations or {}
    head = _('Title and cover')
    for name, kind, cap in SITE_FIELDS:
        add(f'site:{name}', kind, getattr(site, name) or '', site_tr.get(language, {}).get(name, ''),
            1, head, _label(name), 'site', site, name, cap, site_tr.get(source_language, {}).get(name, ''),
            {'block_id': ''})
    # Page by page (change site-pages): the page's title, then its blocks. `n` numbers the table's
    # groups; it is a label, never a key.
    pages = sites.pages_for(site)
    n = 1
    for site_page in pages:
        ptr = site_page.translations or {}
        if len(pages) > 1:
            n += 1
            add(f'page:{site_page.pk}:title', PLAIN, site_page.title, ptr.get(language, {}).get('title', ''),
                n, f'{_("Page")}: {site_page.title}'[:90], _('Page title'), 'page', site_page, 'title',
                sites.PAGE_TITLE_MAX, ptr.get(source_language, {}).get('title', ''),
                {'block_id': '', 'page_id': site_page.pk})
        for block in sites.blocks_for(site, site_page):
            n += 1
            tr = block.translations or {}
            label = sites.outline_label(block) or str(sites.BLOCK_KINDS[block.kind][0])
            page_title = f'{n - 1}. {sites.BLOCK_KINDS[block.kind][0]}' + (f': {label}' if label else '')
            if len(pages) > 1:
                page_title = f'{site_page.title} · {page_title}'
            page_title = page_title[:90]
            for name, kind, cap, source in block_fields(block):
                add(f'block:{block.pk}:{name}', kind, source, tr.get(language, {}).get(name, ''),
                    n, page_title, _label(name), 'block', block, name, cap,
                    tr.get(source_language, {}).get(name, ''), {'block_id': block.pk, 'page_id': site_page.pk})
    # Updates (change site-updates): one group per update, drafts too, newest first.
    for update in sites.feed(site, drafts=True):
        n += 1
        utr = update.translations or {}
        group = f'{_("Update")}: {update.title}'[:90]
        for name, kind, cap in UPDATE_FIELDS:
            if name == 'said' and update.kind != 'decision':
                continue
            add(f'update:{update.pk}:{name}', kind, getattr(update, name) or '', utr.get(language, {}).get(name, ''),
                n, group, _update_label(update, name), 'update', update, name, cap,
                utr.get(source_language, {}).get(name, ''), {'block_id': '', 'update_id': update.pk})
    return out


def _update_label(update, name):
    if name == 'said':
        return _('You said')
    if name == 'body':
        return _('We did') if update.kind == 'decision' else _('Text')
    return _('Title')


def apply(actor, site, language, values, *, overwrite=False, clear_empty=False):
    """`translation_table.apply` for a site: `values = {group or occurrence key: text}`."""
    from .services import sites as site_service
    if language not in languages(site)[1:]:
        raise ValueError(language)
    report = tt.Report()
    occs = occurrences(site, language)
    by_occurrence = {o.key: o for o in occs}
    by_group = {}
    for occ in occs:
        by_group.setdefault(tt.group_key(occ.source, occ.kind), []).append(occ)
    planned = []
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
                    planned.append((occ, ''))
                    report.cleared += 1
                continue
            if existing and not overwrite and existing != text:
                report.skipped += 1
                continue
            if existing and existing != text:
                report.overwritten += 1
            elif not existing:
                report.filled += 1
            planned.append((occ, text))
    if planned:
        site_service.set_translations(actor, site, language, [(o.entity_kind, o.entity, o.field, t) for o, t in planned])
    return report


UPDATE_FIELDS = (('title', PLAIN, 160), ('said', PLAIN, 2000), ('body', RICH, None))


def localize(site, blocks, lang, pages=(), updates=()):
    """Put the `lang` translations on the in-memory site, pages, blocks and updates the public page
    draws (never saved): a missing translation keeps the primary text. Documents blocks get `file_list`."""
    for block, _card in blocks:
        if block.kind in ('documents', 'gallery', 'compare'):
            block.file_list = list(block.files.all())
    if lang == site.language:
        return
    shown = list(updates)
    for block, card in blocks:
        if block.kind == 'updates' and card:
            shown.extend(card['updates'])
    for update in shown:
        row = (update.translations or {}).get(lang) or {}
        for name, _kind, _cap in UPDATE_FIELDS:
            if row.get(name):
                setattr(update, name, row[name])
    for page in pages:
        value = ((page.translations or {}).get(lang) or {}).get('title')
        if value:
            page.title = value
    for name, _kind, _cap in SITE_FIELDS:
        value = (site.translations or {}).get(lang, {}).get(name)
        if value:
            setattr(site, name, value)
    for block, _card in blocks:
        tr = (block.translations or {}).get(lang) or {}
        if not tr:
            continue
        data = copy.deepcopy(block.data) if isinstance(block.data, dict) else {}
        if tr.get('title'):
            block.title = tr['title']
        for name, _kind, _cap in DATA_FIELDS.get(block.kind, ()):
            if tr.get(name):
                data[name] = tr[name]
        if block.kind in ROW_FIELDS:
            key, prefix, fields = ROW_FIELDS[block.kind]
            for i, item in enumerate(data.get(key) or []):
                for name, _kind, _cap in fields:
                    value = tr.get(f'{prefix}:{i}:{name}')
                    if value and isinstance(item, dict):
                        item[name] = value
        if block.kind in ('documents', 'gallery'):
            for f in block.file_list:
                f.title = tr.get(f'file:{f.pk}') or f.title
        block.data = data


def pick_language(request, site):
    """The language a visitor reads the site in: `?lang=`, then the `p_lang` cookie, then the
    browser's Accept-Language, then the primary. Only offered languages count."""
    offered = languages(site)
    asked = (request.GET.get('lang') or '').lower()
    if asked in offered:
        return asked
    cookie = (request.COOKIES.get('p_lang') or '').lower()
    if cookie in offered:
        return cookie
    from django.utils.translation.trans_real import parse_accept_lang_header
    for code, _q in parse_accept_lang_header(request.META.get('HTTP_ACCEPT_LANGUAGE', '')):
        base = code.split('-')[0].lower()
        if base in offered:
            return base
    return site.language
