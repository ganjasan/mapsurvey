"""Demo-survey resolution and demo-open recording.

Moved out of the retired `acquisition` module (GSC/Plausible sync) when the top of
the funnel moved to PostHog's native warehouse sources. Unlike everything that
went with it, this reads our own tables only and is consulted on the respondent
request path, so it has to stay cheap and fail-open.
"""

from django.conf import settings


# -- demo survey resolution ---------------------------------------------------


def demo_survey_uuid():
    """The UUID embedded in `DEMO_SURVEY_URL`, or None if absent/malformed."""
    import re
    import uuid as uuid_module

    url = getattr(settings, 'DEMO_SURVEY_URL', '') or ''
    match = re.search(
        r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', url, re.I
    )
    if not match:
        return None
    try:
        return uuid_module.UUID(match.group(0))
    except ValueError:
        return None


def demo_survey():
    """The `SurveyHeader` behind `DEMO_SURVEY_URL`, or None.

    None covers every way this can be absent -- unset URL, malformed URL, deleted
    survey -- because none of them may raise on a respondent's request path (D4).
    """
    from .models import SurveyHeader

    survey_uuid = demo_survey_uuid()
    if survey_uuid is None:
        return None
    return SurveyHeader.objects.filter(uuid=survey_uuid).first()


def demo_survey_id():
    """The demo survey's primary key, cached, or None.

    Cached because this is consulted on every respondent session creation across the
    whole platform. The cache key includes the configured URL, so changing the setting
    (or overriding it in a test) resolves afresh rather than serving a stale survey.
    """
    from django.core.cache import cache

    url = getattr(settings, 'DEMO_SURVEY_URL', '') or ''
    if not url:
        return None
    key = f'demo_survey_id:{url}'
    try:
        cached = cache.get(key)
    except Exception:                                # cache backend down
        cached = None
    if cached is not None:
        return cached or None                        # 0 is the cached "no such survey"

    survey = demo_survey()
    resolved = survey.pk if survey else 0
    try:
        cache.set(key, resolved, 300)
    except Exception:
        pass
    return resolved or None


def record_demo_open(session, request=None):
    """Record that a demo session was started, and by whom if signed in.

    Written only for the demo survey; every other survey's sessions stay free of
    respondent identity (design D4). Failure-tolerant on purpose: analytics must never
    break a respondent's survey.
    """
    from .models import DemoOpen

    try:
        demo_id = demo_survey_id()
        if demo_id is None or session.survey_id != demo_id:
            return None
        user = getattr(request, 'user', None) if request is not None else None
        if user is not None and not getattr(user, 'is_authenticated', False):
            user = None
        return DemoOpen.objects.create(session=session, user=user)
    except Exception:
        logger.exception('recording a demo open failed for session %s', session.pk)
        return None
