"""The connections page (session-authenticated, an editor page) and `/api/v1/me`
(the first bearer-authenticated endpoint)."""
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
from .decorators import api_endpoint
from .forms import PersonalTokenForm
from .models import AUDIENCE_API, KIND_PERSONAL, TokenProfile

SESSION_ONCE_KEY = 'api_token_once'


@api_endpoint(AUDIENCE_API)
def me(request):
    p = request.principal
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
