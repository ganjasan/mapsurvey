from .models import Membership, Organization


class ActiveOrgMiddleware:
    """
    Populate request.active_org from session['active_org_id'].
    Falls back to the user's first membership if the session value is invalid.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.active_org = None

        if request.user.is_authenticated:
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

        return self.get_response(request)
