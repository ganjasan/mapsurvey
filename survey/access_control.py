from django.http import Http404
from django.shortcuts import redirect, render

from .permissions import get_effective_survey_role, SURVEY_ROLE_RANK


def check_survey_access(request, survey):
    """Check if the current request is allowed to access the survey.

    Returns None if access is allowed, or an HttpResponse to return instead.
    """
    # Editors and owners always bypass access control
    if request.user.is_authenticated:
        role = get_effective_survey_role(request.user, survey)
        if role and SURVEY_ROLE_RANK.get(role, -1) >= SURVEY_ROLE_RANK.get('editor', 99):
            return None

    status = survey.status

    if status == 'draft':
        raise Http404

    if status == 'testing':
        return _check_testing_access(request, survey)

    if status == 'published':
        return _check_published_access(request, survey)

    if status in ('closed', 'archived'):
        return render(request, 'survey_closed.html', {'survey': survey})

    return None


def _check_testing_access(request, survey):
    """Testing surveys require a valid test token or password (if set)."""
    session_key = f'test_access_{survey.id}'

    # Already validated in this session
    if request.session.get(session_key):
        return None

    # Check token in query params
    token = request.GET.get('token')
    if token:
        try:
            import uuid as uuid_module
            parsed = uuid_module.UUID(str(token))
            if parsed == survey.test_token:
                request.session[session_key] = True
                return None
        except (ValueError, AttributeError):
            pass

    # If no password set, allow open access in testing
    if not survey.has_password():
        return None

    # Check password session
    password_key = f'survey_password_{survey.id}'
    if request.session.get(password_key):
        return None

    # No valid access — redirect to password page
    from django.urls import reverse
    return redirect(reverse('survey_password_gate', kwargs={'survey_slug': str(survey.uuid)}))


def _check_published_access(request, survey):
    """Published surveys are open unless password-protected."""
    if not survey.has_password():
        return None

    password_key = f'survey_password_{survey.id}'
    if request.session.get(password_key):
        return None

    from django.urls import reverse
    return redirect(reverse('survey_password_gate', kwargs={'survey_slug': str(survey.uuid)}))
