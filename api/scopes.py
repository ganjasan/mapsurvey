"""The scopes registry: the one list the token form, the OAuth consent page and
every scope check read.

A scope is an upper bound, never a grant: a token with `surveys:write` still
cannot edit a survey its user is a viewer on (`api.rights`). Publish and delete
are their own scopes so that a creator can hand an agent the editing keys
without the irreversible ones; the forms leave them unchecked.

No Django models here -- `settings.py` imports this module to fill
`OAUTH2_PROVIDER["SCOPES"]`.
"""
from django.utils.translation import gettext_lazy as _

SURVEYS_READ = 'surveys:read'
SURVEYS_WRITE = 'surveys:write'
SURVEYS_PUBLISH = 'surveys:publish'
SURVEYS_DELETE = 'surveys:delete'
RESPONSES_READ = 'responses:read'
RESPONSES_MODERATE = 'responses:moderate'

# Ordered: this is the order forms and the consent page list them in. Plain
# strings here because settings.py reads this dict before the app registry is
# ready; the forms translate through LABELS.
SCOPES = {
    SURVEYS_READ: 'Read surveys, sections and questions',
    SURVEYS_WRITE: 'Create and edit surveys, sections and questions',
    SURVEYS_PUBLISH: 'Publish, close and reopen surveys',
    SURVEYS_DELETE: 'Delete surveys',
    RESPONSES_READ: 'Read and export responses',
    RESPONSES_MODERATE: 'Approve, hold or reject responses',
}
LABELS = {
    SURVEYS_READ: _('Read surveys, sections and questions'),
    SURVEYS_WRITE: _('Create and edit surveys, sections and questions'),
    SURVEYS_PUBLISH: _('Publish, close and reopen surveys'),
    SURVEYS_DELETE: _('Delete surveys'),
    RESPONSES_READ: _('Read and export responses'),
    RESPONSES_MODERATE: _('Approve, hold or reject responses'),
}

WRITE_SCOPES = frozenset({SURVEYS_WRITE, SURVEYS_PUBLISH, SURVEYS_DELETE})

# Checked by default on the token form; the consent page (#313) does the same
# for a client that asks for more than these.
DEFAULT_SCOPES = (SURVEYS_READ, SURVEYS_WRITE, RESPONSES_READ)

# Off unless the creator switches them on: these are the calls that cannot be undone.
DANGEROUS_SCOPES = frozenset({SURVEYS_PUBLISH, SURVEYS_DELETE})

# Every scope the consent page shows as a switch, off by default: the
# irreversible ones, plus moderation (change api-v2-responses, D6) -- it can be
# changed back, but it decides what leaves exports and public results.
SWITCH_SCOPES = DANGEROUS_SCOPES | {RESPONSES_MODERATE}
SWITCH_NOTES = {
    SURVEYS_PUBLISH: _('This cannot be undone. Off unless you want this app to do it.'),
    SURVEYS_DELETE: _('This cannot be undone. Off unless you want this app to do it.'),
    RESPONSES_MODERATE: _('Rejected responses leave exports and public results; you can change it back.'),
}


def is_valid(scope):
    return scope in SCOPES


def normalize(scopes):
    """A frozen set of known scopes in registry order; unknown ones raise."""
    unknown = [s for s in scopes if s not in SCOPES]
    if unknown:
        raise ValueError(f'unknown scope(s): {", ".join(unknown)}')
    return frozenset(s for s in SCOPES if s in set(scopes))


def to_string(scopes):
    """Space-separated, registry order -- the form django-oauth-toolkit stores."""
    wanted = set(scopes)
    return ' '.join(s for s in SCOPES if s in wanted)
