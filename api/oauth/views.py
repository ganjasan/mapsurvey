"""Consent page with its memory, and DCR behind the limiter (change oauth-server, D6, D8).

The toolkit's `AuthorizationView.get()` validates the request, loads the
application and renders. Ours runs four things in front of it -- the `state`
cap, the inactive-account guard, the audience check and the grant memory --
by validating the request once itself (the toolkit will validate it again;
that costs no query the second time) and otherwise defers to the toolkit.
Errors go through the toolkit's own `error_response`, which redirects only
when oauthlib says the `redirect_uri` is trustworthy and renders our error
branch otherwise.
"""
import logging

from django.utils.translation import gettext as _
from oauth2_provider.exceptions import FatalClientError, OAuthToolkitError
from oauth2_provider.models import RefreshToken, get_application_model
from oauth2_provider.settings import oauth2_settings
from oauth2_provider.views import AuthorizationView as DotAuthorizationView
from oauth2_provider.views import DynamicClientRegistrationManagementView, DynamicClientRegistrationView
from oauthlib.oauth2.rfc6749 import errors as oauthlib_errors

from billing.entitlements import for_organization
from survey import product_events as pe
from survey.audit import audit
from survey.models import Membership

from .. import scopes as scope_registry
from ..gates import FEATURE
from . import audiences, dcr
from .forms import ConsentForm, switch_name
from .grants import client_host, display_name

logger = logging.getLogger(__name__)

STATE_MAX_BYTES = 512


def _page_error(code, description):
    """An error the toolkit renders as a page, never a redirect: its
    `error_response` keys that decision on the WRAPPER being the toolkit's
    FatalClientError. oauthlib keeps the code on the class, hence the subclass."""
    error_class = type('PageError', (oauthlib_errors.FatalClientError,), {'error': code})
    return FatalClientError(error=error_class(description=description))


class AuthorizationView(DotAuthorizationView):
    template_name = 'api/authorize.html'
    form_class = ConsentForm

    # -- GET: guards, audience, memory, then the toolkit --------------------------------

    def get(self, request, *args, **kwargs):
        state = request.GET.get('state', '')
        if len(state.encode('utf-8')) > STATE_MAX_BYTES:
            return self.error_response(_page_error('invalid_request', 'state is longer than 512 bytes'), None)
        if not request.user.is_active:
            return self.error_response(_page_error('access_denied', 'this account is not active'), None)

        try:
            scopes, credentials = self.validate_authorization_request(request)
        except OAuthToolkitError as error:
            return self.error_response(error, application=None)

        application = get_application_model().objects.get(client_id=credentials['client_id'])
        resources = request.GET.getlist('resource')
        try:
            audiences.for_resources(resources)
        except audiences.UnknownResource as exc:
            error = OAuthToolkitError(
                error=audiences.invalid_target(exc.resource, state=credentials.get('state')),
                redirect_uri=credentials['redirect_uri'],
            )
            return self.error_response(error, application)

        if not application.skip_authorization and self.remembered(request.user, application, scopes):
            if resources:
                credentials['resource'] = resources
            try:
                uri, headers, body, status = self.create_authorization_response(
                    request=request, scopes=' '.join(scopes), credentials=credentials, allow=True,
                )
            except OAuthToolkitError as error:
                return self.error_response(error, application)
            self._record_consent(request, application, scopes, remembered=True)
            return self.redirect(uri, application)

        return super().get(request, *args, **kwargs)

    @staticmethod
    def remembered(user, application, scopes):
        """An unrevoked refresh token for this client whose access token covers
        every requested scope. The toolkit's own `auto` prompt looks at live
        access tokens, which last an hour; a grant lasts as long as its
        refresh token."""
        live = (RefreshToken.objects
                .filter(user=user, application=application, revoked__isnull=True, access_token__isnull=False)
                .select_related('access_token'))
        return any(rt.access_token.allow_scopes(scopes) for rt in live)

    # -- the page ---------------------------------------------------------------------

    def get_initial(self):
        initial = super().get_initial()
        scopes = (initial.get('scope') or '').split()
        initial['requested'] = ConsentForm.sign_requested(scopes)
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        application = ctx.get('application')
        scopes = list(ctx.get('scopes') or [])
        if application is not None:
            ctx['client_name'] = display_name(application)
            ctx['client_host'] = client_host(application)
        ctx['redirect_host'] = _host_of(ctx.get('redirect_uri') or '')
        ctx['granted'] = [(s, scope_registry.LABELS.get(s, s)) for s in scopes
                          if s not in scope_registry.SWITCH_SCOPES]
        form = ctx.get('form')
        ctx['switches'] = [(s, scope_registry.LABELS.get(s, s), form[switch_name(s)] if form else None,
                            scope_registry.SWITCH_NOTES.get(s, ''))
                           for s in scopes if s in scope_registry.SWITCH_SCOPES]
        memberships = (Membership.objects.filter(user=self.request.user)
                       .select_related('organization').order_by('organization__name'))
        workspaces = []
        for m in memberships:
            ent = for_organization(m.organization)
            workspaces.append({'name': m.organization.name, 'plan': ent.plan, 'api': ent.has(FEATURE)})
        # The ones the app can actually work in first (change consent-workspaces-table).
        workspaces.sort(key=lambda w: (not w['api'], w['name'].casefold()))
        ctx['workspaces'] = workspaces
        ctx['pro_count'] = sum(1 for w in workspaces if w['api'])
        ctx['any_pro'] = ctx['pro_count'] > 0
        return ctx

    # -- POST: allow / cancel ------------------------------------------------------------

    def form_valid(self, form):
        response = super().form_valid(form)
        location = response.get('Location', '') if hasattr(response, 'get') else ''
        if form.cleaned_data.get('allow') and location and 'error=' not in location:
            application = get_application_model().objects.get(client_id=form.cleaned_data['client_id'])
            self._record_consent(self.request, application, (form.cleaned_data.get('scope') or '').split(),
                                 remembered=False)
        return response

    @staticmethod
    def _record_consent(request, application, scopes, remembered):
        resources = request.GET.getlist('resource') or (request.POST.get('resource') or '').split()
        try:
            auds = audiences.for_resources(resources)
        except audiences.UnknownResource:
            auds = []
        audit(request, 'oauth_consent', client_id=application.client_id, application_id=application.pk,
              scopes=list(scopes), audiences=auds)
        pe.emit(pe.OAUTH_APP_CONNECTED, request.user.pk, {
            'application_id': application.pk, 'scopes': list(scopes), 'audiences': auds, 'remembered': remembered,
        })


def _host_of(uri):
    from urllib.parse import urlsplit
    try:
        return urlsplit(uri).hostname or ''
    except ValueError:
        return ''


class RegistrationView(DynamicClientRegistrationView):
    """RFC 7591 behind the per-IP budget and the body normalisation (D8)."""

    def post(self, request, *args, **kwargs):
        if not oauth2_settings.DCR_ENABLED:
            return super().post(request, *args, **kwargs)
        is_limited, retry_after = dcr.limited(request)
        if is_limited:
            return dcr.rate_limited_response(retry_after)
        error = dcr.rewrite_body(request)
        if error is not None:
            return error
        return super().post(request, *args, **kwargs)


class ManagementView(DynamicClientRegistrationManagementView):
    """RFC 7592: an update is a full replacement, normalised the same way."""

    def put(self, request, client_id, *args, **kwargs):
        error = dcr.rewrite_body(request)
        if error is not None:
            return error
        return super().put(request, client_id, *args, **kwargs)
