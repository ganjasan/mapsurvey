from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import HttpResponseForbidden
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string

from .models import Organization, Membership, Invitation
from .permissions import get_org_membership, ORG_ROLE_RANK


# ─── Organization Switcher ───────────────────────────────────────────────────

@login_required
@require_POST
def switch_org(request):
    """Switch active organization (stored in session)."""
    org_id = request.POST.get('org_id')
    if org_id:
        try:
            membership = Membership.objects.get(user=request.user, organization_id=org_id)
            request.session['active_org_id'] = membership.organization_id
        except Membership.DoesNotExist:
            pass
    return redirect('editor')


# ─── Organization CRUD ───────────────────────────────────────────────────────

@login_required
def org_create(request):
    """Create a new organization. Any authenticated user can create orgs."""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Organization name is required.')
            return render(request, 'org/org_new.html')

        org = Organization(name=name)
        org.save()  # auto-generates slug
        Membership.objects.create(user=request.user, organization=org, role='owner')
        request.session['active_org_id'] = org.id
        messages.success(request, f"Organization '{org.name}' created.")
        return redirect('editor')

    return render(request, 'org/org_new.html')


@login_required
def org_settings(request, slug):
    """Edit organization settings. Owner only."""
    org = get_object_or_404(Organization, slug=slug)
    membership = get_org_membership(request.user, org)
    if not membership or membership.role != 'owner':
        return HttpResponseForbidden()

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        new_slug = request.POST.get('slug', '').strip()
        if name:
            org.name = name
        if new_slug and new_slug != org.slug:
            if Organization.objects.filter(slug=new_slug).exclude(pk=org.pk).exists():
                messages.error(request, f"Slug '{new_slug}' is already taken.")
            else:
                org.slug = new_slug
        org.save()
        messages.success(request, 'Organization settings updated.')
        return redirect('org_settings', slug=org.slug)

    return render(request, 'org/org_settings.html', {'org': org})


# ─── Member Management ───────────────────────────────────────────────────────

@login_required
def org_members(request, slug):
    """List members and pending invitations."""
    org = get_object_or_404(Organization, slug=slug)
    membership = get_org_membership(request.user, org)
    if not membership:
        return HttpResponseForbidden()

    members = (
        Membership.objects
        .filter(organization=org)
        .select_related('user')
        .order_by('joined_at')
    )
    invitations = (
        Invitation.objects
        .filter(organization=org, accepted_at__isnull=True)
        .order_by('-created_at')
    )

    can_manage = membership.role in ('owner', 'admin')
    is_owner = membership.role == 'owner'

    return render(request, 'org/org_members.html', {
        'org': org,
        'members': members,
        'invitations': invitations,
        'can_manage': can_manage,
        'is_owner': is_owner,
        'my_role': membership.role,
        'role_choices': [c[0] for c in Membership._meta.get_field('role').choices],
    })


@login_required
@require_POST
def org_change_role(request, slug, user_id):
    """Change a member's role."""
    org = get_object_or_404(Organization, slug=slug)
    my_membership = get_org_membership(request.user, org)
    if not my_membership or my_membership.role not in ('owner', 'admin'):
        return HttpResponseForbidden()

    try:
        target_membership = Membership.objects.get(organization=org, user_id=user_id)
    except Membership.DoesNotExist:
        messages.error(request, 'Member not found.')
        return redirect('org_members', slug=slug)

    # Admin cannot change owner roles
    if my_membership.role == 'admin' and target_membership.role == 'owner':
        return HttpResponseForbidden()

    new_role = request.POST.get('role')
    if new_role not in dict(Membership._meta.get_field('role').choices):
        messages.error(request, 'Invalid role.')
        return redirect('org_members', slug=slug)

    # Admin cannot promote to owner
    if my_membership.role == 'admin' and new_role == 'owner':
        return HttpResponseForbidden()

    target_membership.role = new_role
    target_membership.save(update_fields=['role'])
    messages.success(request, f"Role updated to '{new_role}'.")
    return redirect('org_members', slug=slug)


@login_required
@require_POST
def org_remove_member(request, slug, user_id):
    """Remove a member from the organization."""
    org = get_object_or_404(Organization, slug=slug)
    my_membership = get_org_membership(request.user, org)
    if not my_membership or my_membership.role not in ('owner', 'admin'):
        return HttpResponseForbidden()

    try:
        target_membership = Membership.objects.get(organization=org, user_id=user_id)
    except Membership.DoesNotExist:
        messages.error(request, 'Member not found.')
        return redirect('org_members', slug=slug)

    # Admin cannot remove owners
    if my_membership.role == 'admin' and target_membership.role == 'owner':
        return HttpResponseForbidden()

    # Cannot remove last owner
    if target_membership.role == 'owner':
        owner_count = Membership.objects.filter(organization=org, role='owner').count()
        if owner_count <= 1:
            messages.error(request, 'Cannot remove the last owner.')
            return redirect('org_members', slug=slug)

    # Remove collaborator entries for this user on org's surveys
    from .models import SurveyCollaborator, SurveyHeader
    org_survey_ids = SurveyHeader.objects.filter(organization=org).values_list('id', flat=True)
    SurveyCollaborator.objects.filter(user_id=user_id, survey_id__in=org_survey_ids).delete()

    target_membership.delete()
    messages.success(request, 'Member removed.')
    return redirect('org_members', slug=slug)


# ─── Invitations ─────────────────────────────────────────────────────────────

@login_required
@require_POST
def org_send_invitation(request, slug):
    """Send an invitation to join the organization."""
    org = get_object_or_404(Organization, slug=slug)
    my_membership = get_org_membership(request.user, org)
    if not my_membership or my_membership.role not in ('owner', 'admin'):
        return HttpResponseForbidden()

    email = request.POST.get('email', '').strip()
    role = request.POST.get('role', 'viewer')

    if not email:
        messages.error(request, 'Email is required.')
        return redirect('org_members', slug=slug)

    # Admin cannot invite as owner
    if my_membership.role == 'admin' and role == 'owner':
        messages.error(request, 'Only owners can invite owners.')
        return redirect('org_members', slug=slug)

    # Replace existing invitation for same email+org
    Invitation.objects.filter(email=email, organization=org).delete()

    invitation = Invitation.objects.create(
        email=email,
        organization=org,
        role=role,
        invited_by=request.user,
    )

    # Send email
    accept_url = request.build_absolute_uri(f'/invitations/{invitation.token}/accept/')
    email_context = {
        'inviter': request.user.username,
        'org_name': org.name,
        'role': role,
        'accept_url': accept_url,
    }
    text_body = render_to_string('org/invitation_email.txt', email_context)
    html_body = render_to_string('org/invitation_email.html', email_context)
    send_mail(
        subject=f"You're invited to join {org.name} on Mapsurvey",
        message=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        html_message=html_body,
        fail_silently=True,
    )

    messages.success(request, f'Invitation sent to {email}.')
    return redirect('org_members', slug=slug)


def accept_invitation(request, token):
    """Accept an invitation to join an organization."""
    try:
        invitation = Invitation.objects.select_related('organization', 'invited_by').get(token=token)
    except Invitation.DoesNotExist:
        if request.user.is_authenticated:
            messages.error(request, 'Invalid invitation link.')
            return redirect('editor')
        return render(request, 'org/invitation_landing.html', {
            'error': 'Invalid invitation link.',
        })

    if invitation.accepted_at:
        if request.user.is_authenticated:
            messages.info(request, 'This invitation has already been used.')
            return redirect('editor')
        return render(request, 'org/invitation_landing.html', {
            'error': 'This invitation has already been used.',
        })

    if invitation.is_expired:
        if request.user.is_authenticated:
            messages.error(request, 'This invitation has expired.')
            return redirect('editor')
        return render(request, 'org/invitation_landing.html', {
            'error': 'This invitation has expired.',
        })

    # Unauthenticated user: store token in session and show landing page
    if not request.user.is_authenticated:
        request.session['pending_invitation_token'] = str(invitation.token)
        return render(request, 'org/invitation_landing.html', {
            'invitation': invitation,
        })

    # Authenticated user: accept immediately
    Membership.objects.get_or_create(
        user=request.user,
        organization=invitation.organization,
        defaults={'role': invitation.role},
    )
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=['accepted_at'])
    request.session['active_org_id'] = invitation.organization_id

    messages.success(request, f"You've joined '{invitation.organization.name}'.")
    return redirect('editor')
