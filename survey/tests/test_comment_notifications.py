"""Tests for the `comment-notifications` capability (openspec/specs/comment-notifications/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import override_settings
from unittest.mock import patch
from django.core import mail as _cm_mail
from survey.models import CommentThread
from survey import comments as _cm
from survey.tasks import send_thread_notification as _cm_task
from survey.tests.helpers import _CommentFixture


class CommentNotificationTest(_CommentFixture):

    def _create(self, actor, anchor, body, mentions=()):
        self.client.login(username=actor.username, password='pw12345678')
        with patch('survey.tasks.send_thread_notification.delay') as delay:
            with self.captureOnCommitCallbacks(execute=True):
                r = self.client.post(self._u('editor_comment_thread_create'), {'anchor': anchor, 'body': body, 'mentions': [str(m) for m in mentions]})
        self.assertEqual(r.status_code, 201)
        return delay

    def _reply(self, actor, thread, body, mentions=()):
        self.client.login(username=actor.username, password='pw12345678')
        with patch('survey.tasks.send_thread_notification.delay') as delay:
            with self.captureOnCommitCallbacks(execute=True):
                r = self.client.post(self._u('editor_comment_reply', thread_id=thread.pk), {'body': body, 'mentions': [str(m) for m in mentions]})
        self.assertEqual(r.status_code, 201)
        return delay

    def test_new_thread_without_mention_notifies_nobody(self):
        """
        GIVEN the owner opens a thread mentioning nobody
        WHEN the transaction commits
        THEN no notification task is queued
        """
        delay = self._create(self.owner, f'question:{self.q1.id}', 'first')
        self.assertEqual(delay.call_count, 0)

    def test_mention_notifies_the_mentioned_member_not_the_actor(self):
        """
        GIVEN the owner opens a thread mentioning the viewer
        WHEN it commits
        THEN exactly one task is queued, for the viewer
        """
        delay = self._create(self.owner, f'question:{self.q1.id}', 'ping', mentions=[self.viewer.pk])
        self.assertEqual(delay.call_count, 1)
        args = delay.call_args[0]
        self.assertEqual(args[3], self.viewer.pk)
        self.assertEqual(args[2], self.owner.pk)

    def test_reply_notifies_thread_author(self):
        """
        GIVEN a thread opened by the owner
        WHEN the viewer replies
        THEN one task is queued for the owner and none for the viewer
        """
        self._create(self.owner, f'section:{self.s1.id}', 'open')
        thread = CommentThread.objects.get()
        delay = self._reply(self.viewer, thread, 'reply')
        recipients = {c[0][3] for c in delay.call_args_list}
        self.assertEqual(recipients, {self.owner.pk})

    def test_earlier_mention_keeps_receiving(self):
        """
        GIVEN the owner mentioned the editor three replies ago
        WHEN the viewer replies without mentioning anyone
        THEN the editor and the owner are both notified, the viewer is not
        """
        self._create(self.owner, f'section:{self.s1.id}', 'open', mentions=[self.editor.pk])
        thread = CommentThread.objects.get()
        self._reply(self.owner, thread, 'r1')
        self._reply(self.owner, thread, 'r2')
        delay = self._reply(self.viewer, thread, 'r3')
        recipients = {c[0][3] for c in delay.call_args_list}
        self.assertEqual(recipients, {self.owner.pk, self.editor.pk})

    @override_settings(SITE_URL='https://test.mapsurvey.org', EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_task_sends_email_with_deep_link(self):
        """
        GIVEN a thread on Q_2 with a comment by the viewer mentioning the owner
        WHEN the notification task runs for the owner
        THEN one email goes to the owner naming the actor and the question, with a SITE_URL deep link ending in #thread-<id>
        """
        _cm_mail.outbox = []
        thread, comment = _cm.open_thread(self.survey, self.viewer, 'question', self.q2.id, 'Can the note ask for a landmark? Cost <€5 & Q&A', [self.owner.pk])
        _cm_task.run(thread.pk, comment.pk, self.viewer.pk, self.owner.pk)
        self.assertEqual(len(_cm_mail.outbox), 1)
        msg = _cm_mail.outbox[0]
        self.assertEqual(msg.to, ['owner@example.com'])
        self.assertIn('Kelsie S', msg.subject)
        self.assertIn('White squirrel', msg.subject)
        self.assertIn('mentioned you', msg.subject)
        self.assertIn('Can the note ask for a landmark? Cost <€5 & Q&A', msg.body)   # text part: no HTML entities
        self.assertIn('Cost &lt;€5 &amp; Q&amp;A', msg.alternatives[0][0])           # html part: escaped
        link = f'https://test.mapsurvey.org/editor/surveys/{self.survey.uuid}/?section={self.s2.id}#thread-{thread.pk}'
        self.assertIn(link, msg.body)
        self.assertEqual(len(msg.alternatives), 1)
        self.assertIn(link, msg.alternatives[0][0])

    def test_task_skips_deleted_comment_and_missing_rows(self):
        """
        GIVEN a deleted comment, or ids that no longer exist
        WHEN the task runs
        THEN nothing is sent and nothing raises
        """
        _cm_mail.outbox = []
        thread, comment = self._open('question', self.q1.id, 'gone', actor=self.viewer)
        _cm.delete_comment(comment)
        _cm_task.run(thread.pk, comment.pk, self.viewer.pk, self.owner.pk)
        _cm_task.run(999999, 999999, self.viewer.pk, self.owner.pk)
        self.assertEqual(len(_cm_mail.outbox), 0)
