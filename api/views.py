"""The connections page (session-authenticated, an editor page), the body of
`/api/v1/me`, and the API's protected-resource metadata (RFC 9728)."""
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from billing.entitlements import for_organization
from survey import product_events as pe
from survey.abuse import client_ip
from survey.audit import audit
from survey.models import CreatorPreferences, Membership

from . import tokens
from .oauth import grants
from .forms import PersonalTokenForm
from .models import KIND_PERSONAL, TokenProfile

SESSION_ONCE_KEY = 'api_token_once'


def me_payload(p):
    """What `GET /api/v1/me` answers (served by the v1 router, api/v1/me.py)."""
    memberships = Membership.objects.filter(user=p.user).select_related('organization').order_by('organization__name')
    if p.organization is not None:
        memberships = memberships.filter(organization=p.organization)
    workspaces = []
    for m in memberships:
        ent = for_organization(m.organization)
        workspaces.append({
            'id': m.organization.pk,
            'slug': m.organization.slug,
            'name': m.organization.name,
            'role': m.role,
            'plan': ent.plan,
            'api': ent.has('api'),
        })
    token = p.profile.token
    return {
        'user': {'id': p.user.pk, 'username': p.user.username, 'email': p.user.email},
        'workspaces': workspaces,
        'token': {
            'kind': p.kind,
            'scopes': sorted(p.scopes),
            'audiences': list(p.profile.audiences),
            'organization': p.organization.slug if p.organization is not None else None,
            'expires': token.expires.isoformat(),
            'label': p.profile.label,
        },
    }


@login_required
@require_http_methods(['GET', 'POST'])
def connections(request):
    """Personal tokens now; connected apps after #313. The MCP interest block
    moved here from the teaser (`agent-access-teaser`), button and event intact."""
    prefs, _created = CreatorPreferences.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'notify':
            if prefs.agent_access_requested_at is None:
                prefs.agent_access_requested_at = timezone.now()
                prefs.save(update_fields=['agent_access_requested_at', 'updated_at'])
                pe.emit(pe.AGENT_ACCESS_REQUESTED, request.user.pk)
            return redirect('editor_account_connections')
        if action == 'revoke':
            return _revoke(request)
        if action == 'disconnect':
            return _disconnect(request)
        form = PersonalTokenForm(request.user, request.POST)
        if form.is_valid():
            return _create(request, form)
    else:
        form = PersonalTokenForm(request.user)

    once = request.session.pop(SESSION_ONCE_KEY, None)
    profiles = (
        TokenProfile.objects
        .filter(token__user=request.user, kind=KIND_PERSONAL, revoked_at__isnull=True)
        .select_related('token', 'organization')
        .order_by('-created_at')
    )
    now = timezone.now()
    rows = [{
        'profile': p,
        'display': tokens.display(p),
        'scopes': p.token.scope.split(),
        'expires': p.token.expires,
        'never_expires': p.token.expires > now.replace(year=now.year + 50),
        'expired': p.token.expires <= now,
    } for p in profiles]
    return render(request, 'api/connections.html', {
        'form': form,
        'rows': rows,
        'apps': grants.connected_apps(request.user),
        'once': once,
        'requested': prefs.agent_access_requested_at is not None,
        'any_pro': any(for_organization(m.organization).has('api')
                       for m in Membership.objects.filter(user=request.user).select_related('organization')),
    })


def _create(request, form):
    cd = form.cleaned_data
    expires = tokens.expires_for(cd['expiry'])
    value, profile = tokens.mint_personal_token(
        request.user, cd['label'], cd['scopes'], cd['audiences'],
        organization=cd['organization'], expires=expires, created_by_ip=client_ip(request),
    )
    audit(request, 'api_token_create', token_id=profile.token_id, label=profile.label,
          scopes=profile.token.scope.split(), audiences=profile.audiences, expires=expires.isoformat())
    pe.emit(pe.API_TOKEN_CREATED, request.user.pk, {
        'scopes': profile.token.scope.split(), 'audiences': profile.audiences, 'expiry': cd['expiry'],
        'bound': profile.organization_id is not None,
    })
    request.session[SESSION_ONCE_KEY] = {'value': value, 'label': profile.label}
    return redirect('editor_account_connections')


def _revoke(request):
    try:
        token_id = int(request.POST.get('token_id', ''))
    except ValueError:
        token_id = None
    profile = TokenProfile.objects.filter(
        token_id=token_id, token__user=request.user, kind=KIND_PERSONAL, revoked_at__isnull=True,
    ).first()
    if profile is None:
        raise Http404()
    tokens.revoke(profile)
    audit(request, 'api_token_revoke', token_id=profile.token_id)
    pe.emit(pe.API_TOKEN_REVOKED, request.user.pk, {'scopes': profile.token.scope.split(),
                                                     'audiences': profile.audiences})
    return redirect('editor_account_connections')


def _disconnect(request):
    """Connected apps (change oauth-server, D9): 404 unless the user holds a
    grant on that application -- another user's grant on the same app included."""
    from oauth2_provider.models import Application
    try:
        application_id = int(request.POST.get('application_id', ''))
    except ValueError:
        application_id = None
    if application_id is None or application_id not in grants.connected_applications(request.user):
        raise Http404()
    application = Application.objects.get(pk=application_id)
    scopes = grants.disconnect(request.user, application)
    audit(request, 'oauth_disconnect', client_id=application.client_id, application_id=application.pk)
    pe.emit(pe.OAUTH_APP_DISCONNECTED, request.user.pk, {'application_id': application.pk, 'scopes': scopes})
    return redirect('editor_account_connections')


def protected_resource_metadata(request):
    """RFC 9728: which authorization server issues tokens for the REST API and
    what they can carry. Public; the API's 401 points here."""
    from django.conf import settings
    from django.http import JsonResponse
    from . import scopes
    response = JsonResponse({
        'resource': settings.API_RESOURCE_URLS['api'],
        'authorization_servers': [settings.OAUTH_ISSUER],
        'scopes_supported': list(scopes.SCOPES),
        'bearer_methods_supported': ['header'],
        'resource_name': 'Mapsurvey REST API',
        'resource_documentation': getattr(settings, 'HELP_SITE_URL', '').rstrip('/') + '/reference/api/'
        if getattr(settings, 'HELP_SITE_URL', '') else settings.OAUTH_ISSUER + '/api/v1/openapi.json',
    })
    response['Access-Control-Allow-Origin'] = '*'
    response['Cache-Control'] = 'public, max-age=3600'
    return response
