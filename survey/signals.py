from django.dispatch import receiver
from django_registration.signals import user_activated

from .models import Organization, Membership


@receiver(user_activated)
def create_personal_org_on_activation(sender, user, request, **kwargs):
    """
    When a new user activates their account, create a personal organization
    and set it as the active org in their session.
    """
    base_name = f"{user.username}'s workspace"
    name = base_name
    base_slug = f"{user.username}-workspace"
    slug = base_slug
    counter = 2

    # Ensure unique slug
    while Organization.objects.filter(slug=slug).exists():
        suffix = f'-{counter}'
        slug = base_slug[:100 - len(suffix)] + suffix
        name = f"{base_name} {counter}"
        counter += 1

    org = Organization.objects.create(name=name, slug=slug)
    Membership.objects.create(user=user, organization=org, role='owner')

    # Set active org in session
    if request and hasattr(request, 'session'):
        request.session['active_org_id'] = org.id

    # Auto-accept any pending invitations for this email
    from .models import Invitation
    from django.utils import timezone
    pending = Invitation.objects.filter(
        email=user.email,
        accepted_at__isnull=True,
    )
    for invite in pending:
        if (timezone.now() - invite.created_at).days <= 7:
            Membership.objects.get_or_create(
                user=user,
                organization=invite.organization,
                defaults={'role': invite.role},
            )
            invite.accepted_at = timezone.now()
            invite.save(update_fields=['accepted_at'])
