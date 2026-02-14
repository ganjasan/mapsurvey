from functools import wraps

from django.http import HttpResponseForbidden, Http404
from django.shortcuts import redirect

from .models import Membership, SurveyCollaborator, SurveyHeader

# Role hierarchy — higher index = more powerful
ORG_ROLE_RANK = {'viewer': 0, 'editor': 1, 'admin': 2, 'owner': 3}
SURVEY_ROLE_RANK = {'viewer': 0, 'editor': 1, 'owner': 2}


def get_org_membership(user, org):
    """Return Membership for user in org, or None."""
    if not user.is_authenticated or org is None:
        return None
    try:
        return Membership.objects.get(user=user, organization=org)
    except Membership.DoesNotExist:
        return None


def _org_role_to_survey_baseline(org_role):
    """
    Map org-level role to implied survey access.
    owner/admin → 'owner' (full control on all surveys)
    editor → None (only own surveys via SurveyCollaborator)
    viewer → 'viewer'
    """
    if org_role in ('owner', 'admin'):
        return 'owner'
    if org_role == 'viewer':
        return 'viewer'
    return None  # editor gets no implicit access to others' surveys


def get_effective_survey_role(user, survey):
    """
    Compute the effective survey role for a user.
    Returns one of: 'owner', 'editor', 'viewer', or None.
    Effective = max(org baseline, explicit SurveyCollaborator role).
    """
    if not user.is_authenticated:
        return None

    org = survey.organization
    membership = get_org_membership(user, org)
    if membership is None:
        return None  # not a member of this org at all

    # Org baseline
    baseline = _org_role_to_survey_baseline(membership.role)

    # Explicit collaborator role
    collab_role = None
    try:
        collab = SurveyCollaborator.objects.get(user=user, survey=survey)
        collab_role = collab.role
    except SurveyCollaborator.DoesNotExist:
        pass

    # Max of baseline and collaborator
    if baseline is None and collab_role is None:
        return None
    if baseline is None:
        return collab_role
    if collab_role is None:
        return baseline

    baseline_rank = SURVEY_ROLE_RANK.get(baseline, -1)
    collab_rank = SURVEY_ROLE_RANK.get(collab_role, -1)
    return baseline if baseline_rank >= collab_rank else collab_role


def _check_org_role(user, org, min_role):
    """Return True if user has at least min_role in org."""
    membership = get_org_membership(user, org)
    if membership is None:
        return False
    return ORG_ROLE_RANK.get(membership.role, -1) >= ORG_ROLE_RANK.get(min_role, 99)


def _check_survey_role(effective_role, min_role):
    """Return True if effective_role meets min_role threshold."""
    if effective_role is None:
        return False
    return SURVEY_ROLE_RANK.get(effective_role, -1) >= SURVEY_ROLE_RANK.get(min_role, 99)


def org_permission_required(min_role='viewer'):
    """
    Decorator for views that require a minimum org-level role.
    The view must accept `request` as first argument.
    Redirects to login if not authenticated, returns 403 if insufficient role.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            if not request.user.is_superuser and not _check_org_role(request.user, request.active_org, min_role):
                return HttpResponseForbidden()
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def survey_permission_required(min_role='viewer', survey_kwarg='survey_uuid'):
    """
    Decorator for views that operate on a specific survey.
    Looks up the survey by UUID from the URL kwargs.
    Returns 404 if survey not in active org.
    Returns 403 if effective role insufficient.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            survey_uuid = kwargs.get(survey_kwarg)
            try:
                survey = SurveyHeader.objects.get(uuid=survey_uuid)
            except SurveyHeader.DoesNotExist:
                raise Http404

            # Must be in active org
            if request.active_org is None or survey.organization_id != request.active_org.id:
                raise Http404

            effective_role = get_effective_survey_role(request.user, survey)
            if not _check_survey_role(effective_role, min_role):
                return HttpResponseForbidden()

            # Attach to request for use in view
            request.survey = survey
            request.effective_survey_role = effective_role
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
