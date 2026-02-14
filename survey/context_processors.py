from django.conf import settings

from .models import Membership


def mapbox(request):
    return {
        'MAPBOX_URL': settings.MAPBOX_URL,
        'MAPBOX_ACCESS_TOKEN': settings.MAPBOX_ACCESS_TOKEN,
    }


def contact(request):
    return {
        'CONTACT_EMAIL': getattr(settings, 'CONTACT_EMAIL', ''),
        'CONTACT_TELEGRAM': getattr(settings, 'CONTACT_TELEGRAM', ''),
    }


def active_org(request):
    """Inject active organization and user's org list into template context."""
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {}

    org = getattr(request, 'active_org', None)
    memberships = (
        Membership.objects
        .filter(user=request.user)
        .select_related('organization')
        .order_by('joined_at')
    )
    user_orgs = [m.organization for m in memberships]
    org_role = None
    for m in memberships:
        if org and m.organization_id == org.id:
            org_role = m.role
            break

    return {
        'active_org': org,
        'user_orgs': user_orgs,
        'org_role': org_role,
    }
