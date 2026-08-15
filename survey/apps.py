from django.apps import AppConfig
from django.conf import settings


class SurveyConfig(AppConfig):
    name = 'survey'

    def ready(self):
        import survey.signals  # noqa: F401

        self._configure_posthog()

    @staticmethod
    def _configure_posthog():
        """Configure the module-level PostHog client for server-side error capture.

        The same POSTHOG_PROJECT_KEY that gates the browser snippet gates this:
        empty key = the client is *explicitly disabled*, so a stray
        capture_exception in a test or management command is a cheap no-op
        rather than an HTTP attempt with an empty key.

        enable_exception_autocapture stays off on purpose. It installs
        sys.excepthook/threading.excepthook process-wide, which under gunicorn
        and Celery prefork double-captures what the two deliberate paths (the
        Django middleware's process_exception and the task_failure receiver in
        mapsurvey/celery.py) already report.
        """
        import posthog

        key = getattr(settings, 'POSTHOG_PROJECT_KEY', '')
        if not key:
            posthog.disabled = True
            return
        posthog.api_key = key
        posthog.host = getattr(settings, 'POSTHOG_API_HOST', '') or 'https://eu.i.posthog.com'
        posthog.disabled = False
