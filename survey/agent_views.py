"""Use your AI assistant: the third way to start (change agent-onboarding, #312).

Three views. The page renders every client's panel from `agent_clients` and the
script only shows and hides them. The status endpoint tells the page that a new
MCP connection exists, so step 1 completes without a click. The request
endpoint records which assistant someone wanted that cannot connect yet.

Nothing here touches the OAuth server or the MCP server; it only reads the token
rows they write.
"""
import datetime

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST

from api.models import AUDIENCE_MCP, KIND_OAUTH, KIND_PERSONAL, TokenProfile
from api.oauth.grants import display_name
from billing.entitlements import for_organization

from . import agent_clients
from . import product_events as pe
from .ai import client as ai_client
from .permissions import org_permission_required

REQUEST_NAME_MAX = 40
# Where the creator came from (`?from=`, change changelog-hero): the back link
# and a property on the page's events. Anything else is dropped, never echoed.
ORIGINS = ('dashboard', 'help', 'connections')


def prompt_templates():
    """The two prompts the page builds from: with a goal ({goal}) and without."""
    return {
        'goal': _('Using the Mapsurvey tools, create a draft map survey to find out: "{goal}". '
                  'Ask me about the place and the survey languages if they are unclear, '
                  'then give me the link to the survey in the Mapsurvey editor.'),
        'empty': _('Using the Mapsurvey tools, help me draft a map survey. First ask me what I '
                   'want to find out, where, and in which languages, then create the draft and '
                   'give me the link to the survey in the Mapsurvey editor.'),
    }


@require_GET
@org_permission_required('editor')
def editor_survey_start_agent(request):
    server_url = settings.MCP_RESOURCE_URL
    selected = request.GET.get('client', '')
    groups = [
        (key, label, [(c, c.panel(server_url)) for c in clients])
        for key, label, clients in agent_clients.grouped()
    ]
    org = request.active_org
    origin = request.GET.get('from', '')
    if origin not in ORIGINS:
        origin = ''
    return render(request, 'editor/survey_start_agent.html', {
        'origin': origin,
        'groups': groups,
        'clients': [pair for _key, _label, pairs in groups for pair in pairs],
        'tag_labels': agent_clients.TAG_LABELS,
        'requested_client': selected if agent_clients.get(selected) else '',
        'default_client': agent_clients.DEFAULT_CLIENT,
        'prompt_targets': agent_clients.PROMPT_TARGET,
        'server_url': server_url,
        'since': timezone.now().isoformat(),
        'needs_pro': not for_organization(org).has('api'),
        'org': org,
        'ai_available': ai_client.provider_configured(),
        'prompts': prompt_templates(),
        'dashboard_url': reverse('editor') + '?dashboard=1',
        'status_strings': {
            'connected_to': _('{client} is connected to Mapsurvey.'),
            'connected': _('Your assistant is connected to Mapsurvey.'),
            'manage': _('Manage connections'),
            'manage_url': reverse('editor_account_connections'),
            'copied': _('Copied'),
            'stopped': _('Still waiting? Reload this page after you press Allow, or use "I\'ve connected".'),
        },
    })


def _new_mcp_connection(user, since):
    """The newest MCP connection the user made after `since`: an OAuth grant
    created then, or a personal token first used then. None when there is none."""
    mcp = TokenProfile.objects.filter(
        token__user=user, revoked_at__isnull=True, audiences__contains=[AUDIENCE_MCP],
    )
    grant = (mcp.filter(kind=KIND_OAUTH, created_at__gt=since, token__application__isnull=False)
             .select_related('token__application').order_by('-created_at').first())
    if grant:
        return {'client': display_name(grant.token.application)}
    if mcp.filter(kind=KIND_PERSONAL, last_used_at__gt=since).exists():
        return {'client': None}
    return None


@require_GET
@login_required
def editor_survey_start_agent_status(request):
    """`{connected, client}` for the signed-in creator. Reveals no token, no
    scope and nothing about anyone else; `since` is the server time the page
    was rendered with, so a skewed browser clock cannot hide a grant."""
    since = parse_datetime(request.GET.get('since', ''))
    if since is None:
        return JsonResponse({'error': 'since'}, status=400)
    if timezone.is_naive(since):
        since = timezone.make_aware(since, datetime.timezone.utc)
    found = _new_mcp_connection(request.user, since)
    if not found:
        return JsonResponse({'connected': False, 'client': None})
    return JsonResponse({'connected': True, 'client': found['client']})


@require_POST
@login_required
def editor_survey_start_agent_request(request):
    """"Tell us which": one event with the assistant's name, nothing stored."""
    name = (request.POST.get('name') or '').strip()[:REQUEST_NAME_MAX]
    if not name:
        return HttpResponse(status=400)
    pe.emit(pe.AGENT_CLIENT_REQUESTED, request.user.pk, {'name': name})
    return HttpResponse(status=204)
