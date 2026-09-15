"""Celery tasks of the survey app that are not AI generation (see survey/ai/tasks.py).

One task per recipient: a bad address retries on its own and never holds the
other participants' mail hostage. `fail_silently=False` on purpose — a
transport failure must raise so Celery retries it and, past the last retry,
the `task_failure` receiver in mapsurvey/celery.py reports it. Silent loss of
a comment notification is the failure this feature exists to prevent.
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_thread_notification(self, thread_id, comment_id, actor_id, recipient_id):
    from django.contrib.auth import get_user_model
    from .comments import display_name, resolve_anchor, thread_path
    from .mail import absolute_url, send_templated_mail
    from .models import Comment, CommentThread

    User = get_user_model()
    try:
        thread = CommentThread.objects.select_related('survey').get(pk=thread_id)
        comment = Comment.objects.select_related('author').prefetch_related('attachments').get(pk=comment_id)
        recipient = User.objects.get(pk=recipient_id)
    except (CommentThread.DoesNotExist, Comment.DoesNotExist, User.DoesNotExist):
        logger.warning('thread notification %s/%s/%s: row gone before send', thread_id, comment_id, recipient_id)
        return
    if not recipient.email or comment.deleted_at is not None:
        return

    actor = comment.author
    anchor = resolve_anchor(thread)
    mentioned = comment.mentions.filter(pk=recipient.pk).exists()
    kind_label = {'survey': 'the survey', 'question': 'the question', 'section': 'the section',
                  'session': 'a response', 'block': 'the results block'}[anchor.kind]
    verb = 'mentioned you on' if mentioned else 'commented on'
    context = {
        'actor_name': display_name(actor),
        'verb': verb,
        'kind_label': kind_label,
        'anchor_label': anchor.label,
        'survey_name': thread.survey.name,
        'body': comment.body,
        'attachments': [a.original_name for a in comment.attachments.all()],
        'thread_url': absolute_url(thread_path(thread, anchor)),
        'mentioned': mentioned,
    }
    subject = f'{context["actor_name"]} {verb} “{anchor.label}” · {thread.survey.name}'
    try:
        send_templated_mail('comments/notify', recipient.email, subject, context, fail_silently=False)
    except Exception as exc:  # noqa: BLE001 — retry, then let task_failure report it
        raise self.retry(exc=exc)
