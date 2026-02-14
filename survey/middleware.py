from .models import Membership, Organization, Invitation


class ActiveOrgMiddleware:
    """
    Populate request.active_org from session['active_org_id'].
    Falls back to the user's first membership if the session value is invalid.
    Also processes pending invitation tokens stored in session.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.active_org = None

        if request.user.is_authenticated:
            # Process pending invitation token from session
            pending_token = request.session.pop('pending_invitation_token', None)
            if pending_token:
                self._process_pending_invitation(request, pending_token)

            org_id = request.session.get('active_org_id')
            if org_id:
                # Verify user still has membership in this org
                try:
                    membership = Membership.objects.select_related('organization').get(
                        user=request.user,
                        organization_id=org_id,
                    )
                    request.active_org = membership.organization
                except Membership.DoesNotExist:
                    # Stale session — fall through to fallback
                    org_id = None

            if not org_id:
                # Fallback: first org by join date
                membership = (
                    Membership.objects
                    .filter(user=request.user)
                    .select_related('organization')
                    .order_by('joined_at')
                    .first()
                )
                if membership:
                    request.active_org = membership.organization
                    request.session['active_org_id'] = membership.organization.id
                elif request.user.is_superuser:
                    # Superusers created via createsuperuser have no membership.
                    # Auto-assign them as owner of the first org.
                    org = Organization.objects.order_by('id').first()
                    if org:
                        membership = Membership.objects.create(
                            user=request.user, organization=org, role='owner',
                        )
                        request.active_org = org
                        request.session['active_org_id'] = org.id

        return self.get_response(request)

    def _process_pending_invitation(self, request, token):
        """Accept a pending invitation stored in the session."""
        from django.contrib import messages
        from django.utils import timezone

        try:
            invitation = Invitation.objects.select_related('organization').get(token=token)
        except Invitation.DoesNotExist:
            return

        if not invitation.is_acceptable:
            return

        Membership.objects.get_or_create(
            user=request.user,
            organization=invitation.organization,
            defaults={'role': invitation.role},
        )
        invitation.accepted_at = timezone.now()
        invitation.save(update_fields=['accepted_at'])
        request.session['active_org_id'] = invitation.organization_id
        messages.success(request, f"You've joined '{invitation.organization.name}'.")
