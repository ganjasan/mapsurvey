"""Before you publish (change reports-review, #706).

What an author is shown before a report goes out: what of it names or places individual people
(every picked quote, every map that shows marks, a threshold of 1), and what would look unfinished
(blocks that render nothing, a map nobody described for screen readers, a report without a title).
Only the first group can hold a publication back, and only until the author confirms having read
it — whether a quote or a mark may go out is the survey owner's decision (owner, 2026-11-16), so
the product makes sure it was a decision.
"""
from dataclasses import dataclass, field

from django.utils.translation import gettext as _
from django.utils.translation import ngettext


@dataclass
class Item:
    key: str            # quote | marks | k | empty | map_description | title | hidden
    message: str
    block_id: int = None
    fix: str = ''       # '' | 'open' (open the block) | 'delete' (delete the block) | 'settings'
    detail: list = field(default_factory=list)


@dataclass
class Checks:
    privacy: list
    other: list

    @property
    def needs_ack(self):
        """Quotes and marks are published only after the author confirmed having read them."""
        return any(item.key in ('quote', 'marks') for item in self.privacy)

    @property
    def clean(self):
        return not self.privacy and not self.other


def _label(block):
    title = (block.custom_title or {}).get('en') if isinstance(block.custom_title, dict) else ''
    if title:
        return title
    question = block.question if block.question_code else None
    if question is not None:
        return question.name or question.code
    return block.get_block_type_display()


def run(report):
    """The checks of a report as it stands now."""
    from reports.quotes import contact_flags
    from reports.render import ReportService
    from reports.sources import attach_questions
    privacy, other = [], []
    blocks = attach_questions(report.blocks.select_related('dataset__survey', 'view__dataset__survey'))
    service = ReportService(report)
    hidden = 0
    for block in blocks:
        if block.is_hidden:
            hidden += 1
            continue
        if block.block_type == 'quotes':
            quotes = [item.get('text', '') for item in (block.config or {}).get('items') or []]
            if quotes:
                privacy.append(Item('quote', ngettext(
                    '%(n)s quote will be published as written. Check that it names nobody.',
                    '%(n)s quotes will be published as written. Check that they name nobody.',
                    len(quotes)) % {'n': len(quotes)}, block.id, 'open', quotes))
                carrying = [text for text in quotes if contact_flags(text)]
                if carrying:
                    privacy.append(Item('quote_contact', ngettext(
                        '%(n)s quote carries an email address, a phone number or a web address.',
                        '%(n)s quotes carry an email address, a phone number or a web address.',
                        len(carrying)) % {'n': len(carrying)}, block.id, 'open', carrying))
        if block.block_type == 'map' and (block.config or {}).get('marks'):
            privacy.append(Item('marks', _('“%(title)s” shows every mark as it was drawn, not squares. '
                                           'A mark can point at someone\'s home.') % {'title': _label(block)},
                                block.id, 'open'))
        if service._build_block(block) is None:
            other.append(Item('empty', _('“%(title)s” has nothing to show and will be left out.')
                              % {'title': _label(block)}, block.id, 'delete'))
        elif block.block_type == 'map' and not ((block.content or {}).get('en') or '').strip():
            other.append(Item('map_description', _('“%(title)s” has no description for people who use a '
                                                   'screen reader.') % {'title': _label(block)}, block.id, 'open'))
    if (report.k_anonymity_threshold or 1) <= 1:
        privacy.append(Item('k', _('Small groups are not hidden: the threshold is 1, so a chart can show '
                                   'one person\'s answer.'), fix='settings'))
    if not ((report.intro or {}).get('title') or {}).get('en') if isinstance((report.intro or {}).get('title'), dict) \
            else not (report.intro or {}).get('title'):
        other.append(Item('title', _('The report has no title.'), fix='settings'))
    if hidden:
        other.append(Item('hidden', ngettext('%(n)s hidden block will not be shown.',
                                             '%(n)s hidden blocks will not be shown.', hidden) % {'n': hidden}))
    return Checks(privacy=privacy, other=other)
