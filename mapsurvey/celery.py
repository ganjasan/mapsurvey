import os

from celery import Celery
from celery.signals import task_failure

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mapsurvey.settings')

app = Celery('mapsurvey')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


@task_failure.connect
def report_task_failure_to_posthog(sender=None, task_id=None, exception=None, **kwargs):
    """Report failed tasks to PostHog error tracking.

    The Django middleware never sees the worker, so without this hook a task
    that dies (an AI generation, an export, an email) fails invisibly -- the
    exact gap error tracking exists to close.

    Everything is swallowed on purpose: an error reporter that can take down
    failure handling is worse than no reporter. Gated by the same key as all
    other PostHog capture -- when unset, `posthog.disabled` is True (set in
    survey.apps.SurveyConfig) and capture_exception is a no-op.
    """
    try:
        import posthog
        from posthog import new_context, tag

        if posthog.disabled:
            return
        with new_context(capture_exceptions=False):
            tag('celery_task_name', getattr(sender, 'name', str(sender)))
            tag('celery_task_id', str(task_id))
            posthog.capture_exception(exception)
    except Exception:
        pass
