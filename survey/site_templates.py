"""Starting points for a new site (change site-templates, #620; Sites v1.1 wave B).

Two sources, one menu ("From a template" next to New site):

- **Starters** — Mapsurvey's own, defined here as block lists and built through the sites service
  like anything a creator adds, so a starter is always valid against `clean_block`. Blocks that
  need the creator's material (a picture, a survey, files, the project area) are added EMPTY: the
  builder shows them with their drop zones, the public page skips them until they are filled in.
- **Workspace templates** — sites saved with *Save as template* (`Site.is_template`): a copy without
  survey links, never published, opened by members like a draft.
"""
from django.utils.translation import gettext_lazy as _

STARTERS = {
    'consultation': {
        'title': _('Consultation'),
        'description': _('One engagement: why we ask, how to take part, what happens next.'),
        'icon': 'fas fa-comments',
        'blocks': [
            ('heading', _('About the project'), {'size': 'l'}),
            ('text', '', {'body': _('<p>What the project is, why residents are asked now, and what is already decided.</p>')}),
            ('survey', _('Take part'), {}),
            ('timeline', _('How it works'), {'items': [
                {'title': _('Tell us what you think'), 'when': '', 'body': ''},
                {'title': _('What we heard'), 'when': '', 'body': ''},
                {'title': _('Decision'), 'when': '', 'body': ''}], 'current': '0'}),
            ('event', _('Meet us'), {}),
            ('faq', _('Questions'), {'items': [
                {'q': _('Who is running this consultation?'), 'a': ''},
                {'q': _('What happens with my answers?'), 'a': ''}]}),
            ('contacts', _('Contact'), {}),
        ],
    },
    'master-plan': {
        'title': _('Master plan'),
        'description': _('A design project over months: the area, the concepts, the documents, the results.'),
        'icon': 'fas fa-drafting-compass',
        'blocks': [
            ('heading', _('The plan'), {'size': 'l'}),
            ('text', '', {'body': _('<p>The place, the people who use it, and what the plan sets out to change.</p>')}),
            ('map', _('Where'), {}),
            ('timeline', _('How the plan is made'), {'items': [
                {'title': _('Listen'), 'when': '', 'body': ''},
                {'title': _('Concepts'), 'when': '', 'body': ''},
                {'title': _('Draft plan'), 'when': '', 'body': ''},
                {'title': _('Final plan'), 'when': '', 'body': ''}], 'current': '0'}),
            ('survey', _('Take part'), {}),
            ('heading', _('What we heard'), {'size': 'l'}),
            ('results', '', {}),
            ('documents', _('Documents'), {}),
            ('contacts', _('Project team'), {}),
        ],
    },
}


def starters():
    return [(key, s['title'], s['description'], s['icon']) for key, s in STARTERS.items()]


def fields_for(kind, data, title):
    """The QueryDict the panel form would post for a starter block."""
    from django.http import QueryDict
    q = QueryDict(mutable=True)
    q['title'] = str(title or '')
    for key, value in (data or {}).items():
        if key == 'items' and kind == 'faq':
            q.setlist('q', [str(i['q']) for i in value])
            q.setlist('a', [str(i['a']) for i in value])
        elif key == 'items' and kind == 'timeline':
            q.setlist('phase_title', [str(i['title']) for i in value])
            q.setlist('phase_when', [str(i['when']) for i in value])
            q.setlist('phase_body', [str(i['body']) for i in value])
        else:
            q[key] = str(value)
    return q
