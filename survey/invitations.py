"""Workspace invitations: the one place an invitation is accepted (change
invite-landing-journey, #512).

Four entry points used to write the acceptance each in their own way -- the
signed-in accept view, the token parked in the session by the landing page, the
address match at email confirmation -- while registration decided where a new
account lives without knowing about any of them. The invitee ended up with a
membership, an unrequested personal workspace, whichever active workspace was
written last, and the start page "How do you want to start?". Every acceptance
now goes through `accept()`; the registration receiver asks `accept_pending()`
BEFORE it creates a personal workspace, and the dashboard reads `take_joined()`
once to show the "You've joined" banner instead of redirecting to the start page.

An invitation LINK (its token was mailed) is the credential, whoever is signed in
and whatever address they typed; an invitation matched by ADDRESS waits for the
confirmation (change login-grace-period, #487) -- that rule lives in
`signals.accept_invitations_on_confirmation`, which calls `join_by_address` here.
"""
from django.core.exceptions import ValidationError
from django.utils import timezone

from . import product_events as pe
from .models import Invitation, Membership

#: Session key the landing page parks the token under. The name predates this
#: module; live sessions carry it, so it stays.
SESSION_TOKEN_KEY = 'pending_invitation_token'
#: Session key naming the workspace joined by the last acceptance; the dashboard
#: pops it once (`take_joined`) to render the banner and skip the start page.
JOINED_KEY = 'ms_joined_org_id'

SURFACE_LINK = 'link'          # signed-in visitor opened the mailed link
SURFACE_REGISTER = 'register'  # the token was parked when the account was created
SURFACE_SIGN_IN = 'sign_in'    # the token was parked, consumed on the first signed-in request
SURFACE_CONFIRM = 'confirm'    # matched by address at email confirmation


def acceptable(token):
    """The invitation `token` names, if it can still be accepted; else None."""
    if not token:
        return None
    try:
        invitation = Invitation.objects.select_related('organization').get(token=token)
    except (Invitation.DoesNotExist, ValidationError, ValueError, TypeError):
        return None  # unknown, or not even a UUID (anything a query string can carry)
    return invitation if invitation.is_acceptable else None


def remember(request, invitation):
    """Park the invitation's token in the session for the sign-in or registration to come."""
    request.session[SESSION_TOKEN_KEY] = str(invitation.token)


def pending(request):
    """The parked invitation, validated; a dead token is dropped from the session."""
    token = request.session.get(SESSION_TOKEN_KEY)
    if not token:
        return None
    invitation = acceptable(token)
    if invitation is None:
        request.session.pop(SESSION_TOKEN_KEY, None)
    return invitation


def accept(invitation, user, request=None, surface=SURFACE_LINK):
    """Make `user` a member of the inviting workspace and mark the invitation used.

    An existing member keeps their role (`get_or_create`). With a request, the
    inviting workspace becomes the active one, the session is marked as having
    just joined it, and the parked token (if any) is forgotten.
    """
    membership, _created = Membership.objects.get_or_create(
        user=user,
        organization=invitation.organization,
        defaults={'role': invitation.role},
    )
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=['accepted_at'])
    if request is not None:
        request.session['active_org_id'] = invitation.organization_id
        request.session[JOINED_KEY] = invitation.organization_id
        request.session.pop(SESSION_TOKEN_KEY, None)
    pe.emit(pe.INVITATION_ACCEPTED, user.pk, {
        'organization_id': invitation.organization_id,
        'role': invitation.role,
        'surface': surface,
    })
    return membership


def accept_pending(request, user, surface=SURFACE_SIGN_IN):
    """Accept the parked invitation for `user`; the workspace joined, or None."""
    invitation = pending(request)
    if invitation is None:
        return None
    accept(invitation, user, request, surface=surface)
    return invitation.organization


def join_by_address(user, request=None):
    """Join every workspace that invited `user.email` and can still be accepted.

    Address alone is proof of nothing until the mailbox is confirmed, so this
    runs from the `user_activated` receiver -- never at registration. With a
    request the LAST workspace joined becomes active and marked, so the
    confirmation's redirect lands on its dashboard with the banner.
    """
    joined = []
    if not user.email:
        return joined
    for invitation in (Invitation.objects.filter(email=user.email, accepted_at__isnull=True)
                       .select_related('organization').order_by('created_at')):
        if not invitation.is_acceptable:
            continue
        accept(invitation, user, request, surface=SURFACE_CONFIRM)
        joined.append(invitation.organization)
    return joined


def take_joined(request):
    """Pop the "just joined" mark: the joined workspace's id, or None."""
    return request.session.pop(JOINED_KEY, None)
