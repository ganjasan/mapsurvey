from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils.text import slugify
from django_registration.signals import user_activated, user_registered

from . import product_events as pe
from .models import Membership, Organization, SurveySession, Upload


@receiver(user_registered)
def create_personal_org_on_registration(sender, user, request, **kwargs):
    """
    When a new user registers, create a personal organization
    and set it as the active org in their session.
    """
    base_name = f"{user.username}'s workspace"
    name = base_name
    base_slug = slugify(f"{user.username}-workspace")[:100] or 'workspace'
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


@receiver(user_registered)
def emit_registration_event(sender, user, request, **kwargs):
    """First step of the creator funnel.

    A separate receiver from the org creation above rather than a line inside
    it: analytics must never be able to break account creation, and keeping the
    two apart makes that structural instead of a promise. `emit` swallows its
    own errors, but a receiver that raised would still abort the signal chain.
    """
    # The attribution row is written here, before the event, so the event can
    # carry the first touch as `$set_once` person properties. The view also calls
    # `persist_signup_attribution` afterwards; that call finds the row and is a
    # no-op, which is the intended belt-and-braces.
    props = None
    try:
        from .events import persist_signup_attribution
        from .models import SignupAttribution
        row = persist_signup_attribution(user, request) if request is not None else None
        row = row or SignupAttribution.objects.filter(user=user).first()
        if row is not None:
            props = {'$set_once': pe.first_touch_properties(row)}
    except Exception:  # analytics never breaks registration
        props = None
    pe.emit(pe.CREATOR_REGISTERED, user.pk, props)


@receiver(user_activated)
def emit_activation_event(sender, user, request, **kwargs):
    """The step the backfill can only approximate.

    No activation timestamp is stored, so historical rows share `date_joined`
    and are tagged `backfill_proxy`. Emitted live from here on, this becomes the
    real moment -- which is why insights comparing activation *lag* must filter
    on `timestamp_source`.
    """
    pe.emit(pe.CREATOR_ACTIVATED, user.pk)


@receiver(post_save, sender=SurveySession)
def emit_first_response_event(sender, instance, created, **kwargs):
    """Last funnel stage: a creator's survey received its first *external* answer.

    A signal rather than three edits in `views.py`, where sessions are created
    in three branches -- one of which would eventually be missed.

    Only sessions of kind `external` count. The owner opening their published
    survey to check it used to fire this event (median 21 minutes after
    publishing, ~100% "conversion"), which made the funnel's last step a fiction.
    Owner, collaborator and preview sessions neither emit nor suppress a later
    external one.

    This fires on a *respondent's* action but is a *creator* milestone, and the
    distinction is the whole boundary: the event is attributed to the survey's
    owner and carries only the survey id and the kind `external`. Nothing about
    the respondent is sent, which is why there is no per-session event here --
    that is `SurveyEvent`'s job, in our own database.
    """
    if not created:
        return
    if instance.opened_by_kind != SurveySession.OPENED_BY_EXTERNAL:
        return
    owner_id = getattr(instance.survey, 'created_by_id', None)
    if owner_id is None:
        return
    already = (SurveySession.objects
               .filter(survey_id=instance.survey_id, is_deleted=False,
                       opened_by_kind=SurveySession.OPENED_BY_EXTERNAL)
               .exclude(pk=instance.pk)
               .exists())
    if already:
        return
    pe.emit(pe.SURVEY_FIRST_RESPONSE, owner_id, {
        'survey_id': str(instance.survey_id),
        # Whether AI-drafted surveys actually collect answers is the end of the
        # hypothesis, and carrying the method here makes it a breakdown rather
        # than a join back to survey_created.
        'creation_method': pe.creation_method_for(instance.survey_id),
        'respondent_kind': SurveySession.OPENED_BY_EXTERNAL,
    })


@receiver(post_delete, sender=Upload)
def delete_upload_object(sender, instance, **kwargs):
    """The stored file follows its row. Rows go away two ways — orphan
    reclamation and the session/survey CASCADE — and both must take the
    object in the bucket (or on disk) with them, or storage grows forever.
    save=False: the row is already gone, there is nothing to update."""
    if instance.file:
        instance.file.delete(save=False)
