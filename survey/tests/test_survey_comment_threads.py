"""Tests for the `survey-comment-threads` capability (openspec/specs/survey-comment-threads/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.utils import timezone
from unittest.mock import patch
import json
from survey.models import SurveyHeader, SurveySection, Question, SurveySession, Answer
from django.core.files.uploadedfile import SimpleUploadedFile as _CmUpload
from django.db import IntegrityError as _CmIntegrityError, transaction as _cm_transaction
from survey.models import CommentThread, Comment, CommentAttachment
from survey import comments as _cm
from survey.versioning import clone_survey_for_draft as _cm_clone, publish_draft as _cm_publish
from survey.tests.helpers import _CommentFixture, _EmptySessionFixture


class CommentThreadModelTest(_CommentFixture):

    def test_one_anchor_constraint(self):
        """
        GIVEN a thread row that names a question AND a section
        WHEN it is saved
        THEN the database rejects it, so no code path can create an ambiguous anchor
        """
        with self.assertRaises(_CmIntegrityError):
            with _cm_transaction.atomic():
                CommentThread.objects.create(survey=self.survey, anchor_kind='question',
                                             question_code='Q_1', section_code='S1')

    def test_anchor_kind_must_match_field(self):
        """
        GIVEN a thread with anchor_kind=section but only a question code
        WHEN it is saved
        THEN the constraint rejects it
        """
        with self.assertRaises(_CmIntegrityError):
            with _cm_transaction.atomic():
                CommentThread.objects.create(survey=self.survey, anchor_kind='section', question_code='Q_1')

    def test_open_thread_stores_code_not_id(self):
        """
        GIVEN a question
        WHEN a thread is opened on it by id
        THEN the thread stores the question's code and the canonical survey
        """
        thread, comment = self._open('question', self.q1.id, 'first')
        self.assertEqual(thread.anchor_kind, 'question')
        self.assertEqual(thread.question_code, 'Q_1')
        self.assertEqual(thread.survey_id, self.survey.id)
        self.assertEqual(comment.body, 'first')
        self.assertEqual(thread.status, 'open')

    def test_soft_delete_keeps_row(self):
        """
        GIVEN a comment with a body
        WHEN it is deleted
        THEN the row stays with an empty body and deleted_at set, and the thread still lists it
        """
        thread, comment = self._open('section', self.s1.id, 'note')
        _cm.delete_comment(comment)
        comment.refresh_from_db()
        self.assertEqual(comment.body, '')
        self.assertIsNotNone(comment.deleted_at)
        self.assertEqual(thread.comments.count(), 1)

    def test_attachment_key_is_random_and_private(self):
        """
        GIVEN an attachment model
        WHEN its upload key is computed
        THEN it lives under comment_attachments/ with a random name and keeps the extension
        """
        from survey.models import comment_attachment_key
        key = comment_attachment_key(None, 'Count Sheet.JPG')
        self.assertTrue(key.startswith('comment_attachments/'))
        self.assertTrue(key.endswith('.jpg'))
        self.assertNotIn('Count', key)


class CommentThreadVersioningTest(_CommentFixture):

    def test_thread_from_draft_survives_publish(self):
        """
        GIVEN a published survey with a thread opened from its DRAFT copy on question Q_1
        WHEN the draft is published
        THEN the thread still resolves to the (new) canonical Q_1 row and shows in the survey's threads
        """
        self.survey.status = 'published'
        self.survey.save()
        draft = _cm_clone(self.survey)
        draft_q = Question.objects.get(survey_section__survey_header=draft, code='Q_1')
        thread, _ = _cm.open_thread(draft, self.owner, 'question', draft_q.id, 'from the draft')
        self.assertEqual(thread.survey_id, self.survey.id)
        _cm_publish(draft)
        thread.refresh_from_db()
        anchor = _cm.resolve_anchor(thread)
        self.assertTrue(anchor.exists)
        self.assertEqual(anchor.kind, 'question')
        new_q = Question.objects.get(survey_section__survey_header=self.survey, code='Q_1')
        self.assertEqual(anchor.object.id, new_q.id)
        self.assertNotEqual(anchor.object.id, self.q1.id)
        self.assertIn(thread, list(_cm.threads_for(self.survey)))

    def test_deleted_question_thread_is_kept_but_marked(self):
        """
        GIVEN a thread on a question
        WHEN the question is deleted
        THEN the thread is still listed, its anchor reports exists=False, and the drawer renders the marker
        """
        thread, _ = self._open('question', self.q1.id)
        self.q1.delete()
        anchor = _cm.resolve_anchor(thread)
        self.assertFalse(anchor.exists)
        response = self.client.get(self._u('editor_comment_threads'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no longer in the survey')
        self.assertEqual(_cm.open_counts(self.survey)['total'], 1)


class CommentThreadEditorTest(_CommentFixture):

    def test_viewer_opens_replies_and_resolves(self):
        """
        GIVEN a viewer
        WHEN they open a thread, reply, and resolve it over the endpoints
        THEN every call succeeds and the thread ends resolved by the viewer
        """
        self.client.login(username='cmviewer', password='pw12345678')
        r = self.client.post(self._u('editor_comment_thread_create'), {'anchor': f'question:{self.q1.id}', 'body': 'wording?'})
        self.assertEqual(r.status_code, 201)
        thread = CommentThread.objects.get()
        r = self.client.post(self._u('editor_comment_reply', thread_id=thread.pk), {'body': 'more'})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(thread.comments.count(), 2)
        r = self.client.post(self._u('editor_comment_resolve', thread_id=thread.pk))
        self.assertEqual(r.status_code, 200)
        thread.refresh_from_db()
        self.assertEqual(thread.status, 'resolved')
        self.assertEqual(thread.resolved_by, self.viewer)
        r = self.client.post(self._u('editor_comment_reopen', thread_id=thread.pk))
        thread.refresh_from_db()
        self.assertEqual(thread.status, 'open')

    def test_editor_cannot_delete_others_comment(self):
        """
        GIVEN a comment written by the owner
        WHEN an editor POSTs delete on it
        THEN the response is 403 and the comment is unchanged
        """
        thread, comment = self._open('section', self.s1.id, 'keep me')
        self.client.login(username='cmeditor', password='pw12345678')
        r = self.client.post(self._u('editor_comment_delete', thread_id=thread.pk, comment_id=comment.pk))
        self.assertEqual(r.status_code, 403)
        comment.refresh_from_db()
        self.assertEqual(comment.body, 'keep me')

    def test_author_deletes_own_comment(self):
        """
        GIVEN a comment written by the viewer
        WHEN the viewer deletes it
        THEN it is soft-deleted
        """
        thread, comment = self._open('section', self.s1.id, 'mine', actor=self.viewer)
        self.client.login(username='cmviewer', password='pw12345678')
        r = self.client.post(self._u('editor_comment_delete', thread_id=thread.pk, comment_id=comment.pk))
        self.assertEqual(r.status_code, 200)
        comment.refresh_from_db()
        self.assertIsNotNone(comment.deleted_at)

    def test_owner_deletes_any_comment(self):
        """
        GIVEN a comment written by the viewer
        WHEN the owner deletes it
        THEN it is soft-deleted and the thread response renders "Comment deleted"
        """
        thread, comment = self._open('section', self.s1.id, 'theirs', actor=self.viewer)
        r = self.client.post(self._u('editor_comment_delete', thread_id=thread.pk, comment_id=comment.pk))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Comment deleted')

    def test_outsider_denied(self):
        """
        GIVEN a signed-in user from another organization
        WHEN they request the drawer or post a thread
        THEN they get 403/404 and nothing is created
        """
        self._open('question', self.q1.id, 'secret wording')
        self.client.login(username='cmoutsider', password='pw12345678')
        r = self.client.get(self._u('editor_comment_threads'))
        self.assertIn(r.status_code, (403, 404))
        self.assertNotIn(b'secret wording', r.content)
        r = self.client.post(self._u('editor_comment_thread_create'), {'anchor': f'question:{self.q1.id}', 'body': 'x'})
        self.assertIn(r.status_code, (403, 404))
        self.assertEqual(CommentThread.objects.count(), 1)

    def test_anonymous_redirected(self):
        """
        GIVEN no session
        WHEN the drawer is requested
        THEN the response redirects to login
        """
        self.client.logout()
        r = self.client.get(self._u('editor_comment_threads'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_html_in_body_is_escaped(self):
        """
        GIVEN a comment whose body carries a script tag
        WHEN the drawer renders it
        THEN the tag appears as text and no script element is emitted
        """
        self._open('question', self.q1.id, '<script>alert(1)</script> hi')
        r = self.client.get(self._u('editor_comment_threads'))
        self.assertContains(r, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(r, '<script>alert(1)</script>')

    def test_mentions_stored_from_ids_and_limited_to_members(self):
        """
        GIVEN a comment posting mention ids for a member and for an outsider
        WHEN it is created
        THEN only the member is stored as a mention and rendered as a chip
        """
        r = self.client.post(self._u('editor_comment_thread_create'), {
            'anchor': f'section:{self.s2.id}', 'body': 'ping @Kelsie',
            'mentions': [str(self.viewer.pk), str(self.outsider.pk)],
        })
        self.assertEqual(r.status_code, 201)
        comment = Comment.objects.get()
        self.assertEqual(list(comment.mentions.all()), [self.viewer])
        self.assertContains(r, '@Kelsie S', status_code=201)

    def test_mentionable_members_include_org_owner_without_collaborator_row(self):
        """
        GIVEN an org owner with no SurveyCollaborator row
        WHEN the member list is requested
        THEN the owner, the viewer and the editor are listed and the outsider is not
        """
        ids = {m.user_id for m in _cm.mentionable_members(self.survey)}
        self.assertEqual(ids, {self.owner.pk, self.viewer.pk, self.editor.pk})
        r = self.client.get(self._u('editor_comment_threads') + f'?anchor=question:{self.q1.id}')
        self.assertContains(r, 'cm-members-question')
        self.assertContains(r, 'editor@example.com')
        self.assertNotContains(r, 'out@example.com')

    def test_bad_anchor_is_404_and_empty_body_is_400(self):
        """
        GIVEN a thread create request
        WHEN the anchor names a question of another survey, or the body is empty
        THEN the responses are 404 and 400 respectively and nothing is created
        """
        other = SurveyHeader.objects.create(name="other", organization=self.org, redirect_url="/", created_by=self.owner)
        os_ = SurveySection.objects.create(survey_header=other, name="x", title="X", code="X1", is_head=True)
        oq = Question.objects.create(survey_section=os_, code="Q_X", order_number=1, name="x", input_type="text")
        r = self.client.post(self._u('editor_comment_thread_create'), {'anchor': f'question:{oq.id}', 'body': 'x'})
        self.assertEqual(r.status_code, 404)
        r = self.client.post(self._u('editor_comment_thread_create'), {'anchor': f'question:{self.q1.id}', 'body': '   '})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(CommentThread.objects.count(), 0)


class CommentBadgeTest(_CommentFixture):

    def test_section_count_includes_questions_inside(self):
        """
        GIVEN two open threads on Q_2 (in S2), one on S2 itself, one resolved on Q_2 and one on S1
        WHEN counts are computed
        THEN Q_2 = 2, S2 = 3, S1 = 1, total = 4 and the resolved thread is not counted
        """
        self._open('question', self.q2.id, 'a')
        self._open('question', self.q2.id, 'b')
        t, _ = self._open('question', self.q2.id, 'c')
        _cm.resolve(t, self.owner)
        self._open('section', self.s2.id, 'd')
        self._open('section', self.s1.id, 'e')
        c = _cm.open_counts(self.survey)
        self.assertEqual(c['question']['Q_2'], 2)
        self.assertEqual(c['section']['S2'], 3)
        self.assertEqual(c['section']['S1'], 1)
        self.assertEqual(c['total'], 4)

    def test_badges_on_survey_page_and_row_endpoints(self):
        """
        GIVEN an open thread on Q_2 and one on S2
        WHEN the survey page, the section panel, the question edit modal and the duplicate endpoint render
        THEN every response carries the badge for the row with its count
        """
        self._open('question', self.q2.id, 'a')
        self._open('section', self.s2.id, 'b')
        r = self.client.get(self._u('editor_survey_detail') + f'?section={self.s2.id}')
        self.assertContains(r, 'data-thread-badge="section:S2"')
        self.assertRegex(r.content.decode(), r'data-thread-badge="section:S2"[^>]*>.*?<span data-cm-n>2</span>')
        self.assertContains(r, 'data-thread-total')
        # The question rows arrive by HTMX from the section panel, never inline on the page.
        r = self.client.get(self._u('editor_section_detail', section_id=self.s2.id), HTTP_HX_REQUEST='true')
        self.assertContains(r, 'data-thread-badge="question:Q_2"')
        self.assertRegex(r.content.decode(), r'data-thread-badge="question:Q_2"[^>]*>.*?<span data-cm-n>1</span>')
        r = self.client.get(self._u('editor_question_edit', question_id=self.q2.id), HTTP_HX_REQUEST='true')
        self.assertContains(r, 'data-cm-open="question:%d"' % self.q2.id)
        r = self.client.post(self._u('editor_question_duplicate', question_id=self.q2.id), HTTP_HX_REQUEST='true')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'data-thread-badge="question:')
        # Paste endpoints bind the survey as `target_survey`; a badge must still render there.
        r = self.client.post(f'/editor/surveys/{self.survey.uuid}/sections/{self.s2.id}/paste-question/',
                             data=json.dumps({'source_survey_uuid': str(self.survey.uuid), 'source_question_id': self.q1.id}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'data-thread-badge="question:')

    def test_counts_endpoint_after_resolve(self):
        """
        GIVEN an open thread on Q_1
        WHEN it is resolved and the counts endpoint is read
        THEN the question key is gone and total is 0
        """
        t, _ = self._open('question', self.q1.id, 'a')
        r = self.client.get(self._u('editor_comment_counts'))
        self.assertEqual(r.json()['counts'].get('question:Q_1'), 1)
        r = self.client.post(self._u('editor_comment_resolve', thread_id=t.pk))
        self.assertIn('threadCountsChanged', r['HX-Trigger'])
        r = self.client.get(self._u('editor_comment_counts'))
        self.assertNotIn('question:Q_1', r.json()['counts'])
        self.assertEqual(r.json()['total'], 0)

    def test_public_results_and_session_detail_carry_threads(self):
        """
        GIVEN a thread on the results block and one on the session
        WHEN the public-results config and the session detail render
        THEN the block row shows the badge and the session detail includes the inline thread
        """
        self._open('block', self.block.id, 'map question')
        self._open('session', self.session.id, 'looks right')
        r = self.client.get(self._u('editor_survey_public_results'))
        self.assertContains(r, 'data-thread-badge="block:%d"' % self.block.id)
        r = self.client.get(self._u('analytics_session_detail', session_id=self.session.id), HTTP_HX_REQUEST='true')
        self.assertContains(r, 'looks right')
        self.assertContains(r, 'data-cm-panel')
        self.assertContains(r, 'name="inline" value="1"')


class CommentAttachmentTest(_CommentFixture):

    def _png(self, name='shot.png', size=100):
        return _CmUpload(name, b'\x89PNG\r\n\x1a\n' + b'0' * size, content_type='image/png')

    def tearDown(self):
        for a in CommentAttachment.objects.all():
            a.file.delete(save=False)

    def test_upload_and_member_download(self):
        """
        GIVEN the viewer posts a thread with a PNG attached
        WHEN a member opens the attachment URL
        THEN the file is returned (200) and its name and kind are recorded
        """
        self.client.login(username='cmviewer', password='pw12345678')
        r = self.client.post(self._u('editor_comment_thread_create'), {'anchor': f'question:{self.q1.id}', 'body': 'see photo', 'files': [self._png()]})
        self.assertEqual(r.status_code, 201)
        att = CommentAttachment.objects.get()
        self.assertEqual(att.kind, 'image')
        self.assertEqual(att.original_name, 'shot.png')
        self.assertTrue(att.file.name.startswith('comment_attachments/'))
        url = self._u('editor_comment_attachment', thread_id=att.comment.thread_id, comment_id=att.comment_id, attachment_id=att.pk)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r['Content-Type'].startswith('image/png'))
        self.assertTrue(b''.join(r.streaming_content).startswith(b'\x89PNG'))

    def test_outsider_cannot_download(self):
        """
        GIVEN an attachment on a thread of this survey
        WHEN a user from another org requests it
        THEN the response is 403/404
        """
        thread, comment = self._open('question', self.q1.id, 'x')
        _cm.attach(comment, [self._png()])
        att = CommentAttachment.objects.get()
        self.client.login(username='cmoutsider', password='pw12345678')
        r = self.client.get(self._u('editor_comment_attachment', thread_id=thread.pk, comment_id=comment.pk, attachment_id=att.pk))
        self.assertIn(r.status_code, (403, 404))

    def test_oversized_and_wrong_type_rejected(self):
        """
        GIVEN a 16 MB file, and an executable
        WHEN either is attached
        THEN the request is 400 with a message and no thread is created
        """
        big = _CmUpload('big.png', b'0' * (16 * 1024 * 1024), content_type='image/png')
        r = self.client.post(self._u('editor_comment_thread_create'), {'anchor': f'question:{self.q1.id}', 'body': 'big', 'files': [big]})
        self.assertEqual(r.status_code, 400)
        self.assertIn(b'15 MB', r.content)
        exe = _CmUpload('run.exe', b'MZ' + b'0' * 10, content_type='application/x-msdownload')
        r = self.client.post(self._u('editor_comment_thread_create'), {'anchor': f'question:{self.q1.id}', 'body': 'exe', 'files': [exe]})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(CommentThread.objects.count(), 0)

    def test_delete_removes_files(self):
        """
        GIVEN a comment with an attachment
        WHEN the comment is deleted
        THEN the attachment row and its file are gone
        """
        thread, comment = self._open('question', self.q1.id, 'x')
        _cm.attach(comment, [self._png()])
        att = CommentAttachment.objects.get()
        storage, name = att.file.storage, att.file.name
        self.assertTrue(storage.exists(name))
        _cm.delete_comment(comment)
        self.assertEqual(CommentAttachment.objects.count(), 0)
        self.assertFalse(storage.exists(name))


class CommentDeepLinkTest(_CommentFixture):

    def test_panel_with_thread_param_focuses_it(self):
        """
        GIVEN two threads on different questions
        WHEN the panel is requested with ?thread=<id of the second>
        THEN the response scopes to that thread's anchor and marks the thread focused
        """
        self._open('question', self.q1.id, 'one')
        t2, _ = self._open('question', self.q2.id, 'two')
        r = self.client.get(self._u('editor_comment_threads') + f'?thread={t2.pk}')
        self.assertContains(r, f'data-focus-thread="{t2.pk}"')
        self.assertContains(r, 'cm-focus')
        self.assertContains(r, 'two')
        self.assertNotContains(r, '>one<')

    def test_anchor_paths_per_kind(self):
        """
        GIVEN one thread per anchor kind
        WHEN their deep-link paths are built
        THEN each points at the right editor page with the object selected and the thread fragment
        """
        Answer.objects.create(survey_session=self.session, question=self.q1, text='answered')
        tq, _ = self._open('question', self.q2.id)
        ts, _ = self._open('section', self.s1.id)
        tse, _ = self._open('session', self.session.id)
        tb, _ = self._open('block', self.block.id)
        u = self.survey.uuid
        self.assertEqual(_cm.thread_path(tq), f'/editor/surveys/{u}/?section={self.s2.id}#thread-{tq.pk}')
        self.assertEqual(_cm.thread_path(ts), f'/editor/surveys/{u}/?section={self.s1.id}#thread-{ts.pk}')
        self.assertEqual(_cm.thread_path(tse), f'/editor/surveys/{u}/analytics/?session={self.session.id}#thread-{tse.pk}')
        self.assertEqual(_cm.thread_path(tb), f'/editor/surveys/{u}/public-results/?block={self.block.id}#thread-{tb.pk}')
        self.assertEqual(_cm.resolve_anchor(tb).label, 'Map · White squirrel')
        self.assertEqual(_cm.resolve_anchor(tse).label, 'Response #1')   # the Responses ordinal, not the db id

    def test_product_events_emitted_without_content(self):
        """
        GIVEN a PostHog emit hook
        WHEN a thread is opened, replied to and resolved
        THEN the three events fire with anchor_kind and survey_id and never the body
        """
        with patch('survey.comment_views.pe.emit') as emit:
            r = self.client.post(self._u('editor_comment_thread_create'), {'anchor': f'question:{self.q1.id}', 'body': 'SECRET BODY'})
            thread = CommentThread.objects.get()
            self.client.post(self._u('editor_comment_reply', thread_id=thread.pk), {'body': 'r'})
            self.client.post(self._u('editor_comment_resolve', thread_id=thread.pk))
        names = [c[0][0] for c in emit.call_args_list]
        self.assertEqual(names, ['comment_thread_opened', 'comment_reply_posted', 'comment_thread_resolved'])
        for c in emit.call_args_list:
            self.assertEqual(c[0][1], self.owner.pk)
            self.assertEqual(c[0][2]['anchor_kind'], 'question')
            self.assertEqual(c[0][2]['survey_id'], self.survey.id)
            self.assertNotIn('SECRET', json.dumps(c[0][2]))


class CommentNewMarksTest(_CommentFixture):
    """"New since you last looked" (UX audit 2026-09-15): CommentSeen per member."""

    def test_other_members_activity_is_new_until_the_drawer_is_opened(self):
        """
        GIVEN the owner opened a thread and the viewer has never looked
        WHEN the viewer loads the drawer twice
        THEN the first render marks the thread new and counts 1 new, the second render marks nothing
        """
        self._open('question', self.q1.id, 'from the owner')
        self.client.login(username='cmviewer', password='pw12345678')
        r = self.client.get(self._u('editor_comment_threads'))
        self.assertContains(r, 'cm-new')
        self.assertContains(r, '1 new')
        r = self.client.get(self._u('editor_comment_threads'))
        self.assertNotContains(r, 'cm-newdot')
        self.assertNotContains(r, 'cm-newpill')

    def test_own_activity_is_never_new(self):
        """
        GIVEN the owner opened a thread themselves
        WHEN the owner loads the drawer
        THEN nothing is marked new
        """
        self._open('question', self.q1.id, 'mine')
        r = self.client.get(self._u('editor_comment_threads'))
        self.assertNotContains(r, 'cm-newdot')

    def test_counts_json_carries_new_keys_and_badges_show_the_dot(self):
        """
        GIVEN the viewer replied in a thread on Q_2 after the owner last looked
        WHEN the owner reads the counts endpoint and the section panel
        THEN the question and its section are listed as new and the badge carries the new mark
        """
        thread, _ = self._open('question', self.q2.id, 'owner opens')
        self.client.get(self._u('editor_comment_threads'))   # owner looks
        _cm.reply(thread, self.viewer, 'viewer answers')
        r = self.client.get(self._u('editor_comment_counts'))
        data = r.json()
        self.assertIn('question:Q_2', data['new'])
        self.assertIn('section:S2', data['new'])
        self.assertEqual(data['new_total'], 1)
        r = self.client.get(self._u('editor_section_detail', section_id=self.s2.id), HTTP_HX_REQUEST='true')
        self.assertRegex(r.content.decode(), r'data-thread-badge="question:Q_2"[^>]*cm-badge--new|cm-badge--new[^>]*data-thread-badge="question:Q_2"')

    def test_resolving_by_the_member_is_not_new_to_them(self):
        """
        GIVEN the owner resolves a thread the viewer opened
        WHEN the owner loads the drawer
        THEN the resolved thread is not marked new for the owner
        """
        thread, _ = self._open('section', self.s1.id, 'viewer opens', actor=self.viewer)
        self.client.get(self._u('editor_comment_threads'))
        _cm.resolve(thread, self.owner)
        r = self.client.get(self._u('editor_comment_threads') + '?status=resolved')
        self.assertNotContains(r, 'cm-newdot')


class CommentEditTest(_CommentFixture):

    def test_author_edits_own_comment_without_a_new_email(self):
        """
        GIVEN a comment by the viewer mentioning the owner
        WHEN the viewer edits its text
        THEN the body changes, edited_at is set, the thread renders "edited", and no notification task is queued
        """
        thread, comment = self._open('question', self.q1.id, 'typo hree', actor=self.viewer, mentions=[self.owner.pk])
        self.client.login(username='cmviewer', password='pw12345678')
        with patch('survey.tasks.send_thread_notification.delay') as delay:
            with self.captureOnCommitCallbacks(execute=True):
                r = self.client.post(self._u('editor_comment_edit', thread_id=thread.pk, comment_id=comment.pk), {'body': 'typo here'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(delay.call_count, 0)
        comment.refresh_from_db()
        self.assertEqual(comment.body, 'typo here')
        self.assertIsNotNone(comment.edited_at)
        self.assertContains(r, 'edited')
        self.assertContains(r, 'typo here')

    def test_others_cannot_edit(self):
        """
        GIVEN a comment by the viewer
        WHEN the owner (any role but the author) posts an edit
        THEN the response is 403 and the body is unchanged
        """
        thread, comment = self._open('question', self.q1.id, 'theirs', actor=self.viewer)
        r = self.client.post(self._u('editor_comment_edit', thread_id=thread.pk, comment_id=comment.pk), {'body': 'mine now'})
        self.assertEqual(r.status_code, 403)
        comment.refresh_from_db()
        self.assertEqual(comment.body, 'theirs')

    def test_edit_form_only_for_own_comments(self):
        """
        GIVEN a thread with one comment by the owner and one by the viewer
        WHEN the owner loads the drawer
        THEN exactly one edit form (for the owner's comment) is rendered
        """
        thread, _ = self._open('section', self.s1.id, 'owner text')
        _cm.reply(thread, self.viewer, 'viewer text')
        r = self.client.get(self._u('editor_comment_threads'))
        self.assertEqual(r.content.decode().count('data-cm-editform'), 1)


class CommentA11yMarkupTest(_CommentFixture):

    def test_controls_have_accessible_names_and_badges_are_buttons(self):
        """
        GIVEN a thread with a comment and the section panel with badges
        WHEN they render
        THEN the close, delete, mention and badge controls carry aria-labels, the textarea is labelled, and the badge is a real button
        """
        thread, comment = self._open('question', self.q2.id, 'a')
        html = self.client.get(self._u('editor_comment_threads') + f'?anchor=question:{self.q2.id}').content.decode()
        for needle in ('aria-label="Close comments"', 'aria-label="Delete comment"', 'aria-label="Mention a member"',
                       'aria-live="polite"' if False else 'aria-pressed=', '<textarea name="body" rows="3" required data-cm-body\n          aria-label='):
            self.assertIn(needle, html)
        rows = self.client.get(self._u('editor_section_detail', section_id=self.s2.id), HTTP_HX_REQUEST='true').content.decode()
        self.assertRegex(rows, r'<button type="button" class="cm-badge[^"]*" data-thread-badge="question:Q_2"')
        self.assertIn('aria-label="1 open comment"', rows)

    def test_session_label_uses_the_responses_ordinal(self):
        """
        GIVEN three answered sessions where the thread is on the second by start time
        WHEN the anchor label is resolved
        THEN it reads Response #2, matching the Responses page numbering, not the database id
        """
        from datetime import timedelta
        base = timezone.now() - timedelta(days=1)
        SurveySession.objects.filter(pk=self.session.pk).update(start_datetime=base)
        s2 = SurveySession.objects.create(survey=self.survey, start_datetime=base + timedelta(hours=1))
        s3 = SurveySession.objects.create(survey=self.survey, start_datetime=base + timedelta(hours=2))
        for sess in (self.session, s2, s3):
            Answer.objects.create(survey_session=sess, question=self.q1, text='answered')
        thread, _ = self._open('session', s2.id, 'second one')
        self.assertEqual(_cm.resolve_anchor(thread).label, 'Response #2')


class CommentDashboardBadgeTest(_CommentFixture):

    def test_dashboard_card_shows_open_and_unseen_counts(self):
        """
        GIVEN a thread the viewer opened on the owner's survey, and one the owner opened themselves
        WHEN the owner loads the dashboard
        THEN the survey card shows 2 open comments and 1 new; after opening the drawer it shows 2 open and nothing new
        """
        self._open('question', self.q1.id, 'from the viewer', actor=self.viewer)
        self._open('section', self.s1.id, 'my own')
        r = self.client.get('/editor/?dashboard=1')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'class="cm-dash-badge cm-dash-badge--new"')
        self.assertContains(r, '1 new')
        self.client.get(self._u('editor_comment_threads'))
        r = self.client.get('/editor/?dashboard=1')
        self.assertContains(r, 'class="cm-dash-badge"')
        self.assertNotContains(r, 'class="cm-dash-badge cm-dash-badge--new"')
        self.assertContains(r, 'aria-label="2 open comments"')

    def test_unseen_by_survey_is_per_member(self):
        """
        GIVEN the owner opened a thread
        WHEN unseen counts are computed for the owner and for the viewer
        THEN the owner sees 0 new and the viewer sees 1 new, both see 1 open
        """
        self._open('question', self.q1.id, 'owner text')
        self.assertEqual(_cm.unseen_by_survey(self.owner, [self.survey])[self.survey.id], (1, 0))
        self.assertEqual(_cm.unseen_by_survey(self.viewer, [self.survey])[self.survey.id], (1, 1))


class CommentGeneralThreadTest(_CommentFixture):
    """The survey itself is the fifth anchor: general threads with no object."""

    def test_general_thread_from_the_whole_survey_view(self):
        """
        GIVEN the drawer opened without an anchor
        WHEN a member posts with anchor survey:all
        THEN a thread with anchor_kind=survey and no object fields is created, listed first under "Survey: general", and the composer stays general
        """
        r = self.client.get(self._u('editor_comment_threads'))
        self.assertContains(r, 'name="anchor" value="survey:all"')
        self._open('question', self.q1.id, 'on a question')
        r = self.client.post(self._u('editor_comment_thread_create'), {'anchor': 'survey:all', 'body': 'When do we send the link?'})
        self.assertEqual(r.status_code, 201)
        t = CommentThread.objects.get(anchor_kind='survey')
        self.assertEqual((t.question_code, t.section_code, t.session_id, t.block_id), ('', '', None, None))
        html = r.content.decode()
        self.assertLess(html.index('Survey:'), html.index('Question:'))
        self.assertContains(r, 'name="anchor" value="survey:all"', status_code=201)
        self.assertEqual(_cm.resolve_anchor(t).label, self.survey.name)
        self.assertEqual(_cm.open_counts(self.survey)['survey']['all'], 1)
        self.assertEqual(_cm.open_counts(self.survey)['total'], 2)

    def test_constraint_still_rejects_a_survey_thread_with_an_object(self):
        """
        GIVEN a survey-kind thread that also names a question
        WHEN it is saved
        THEN the database rejects it
        """
        with self.assertRaises(_CmIntegrityError):
            with _cm_transaction.atomic():
                CommentThread.objects.create(survey=self.survey, anchor_kind='survey', question_code='Q_1')

    def test_general_thread_is_new_for_the_other_member(self):
        """
        GIVEN the owner opened a general thread
        WHEN the viewer reads the counts
        THEN survey:all is listed as new
        """
        self.client.post(self._u('editor_comment_thread_create'), {'anchor': 'survey:all', 'body': 'hello all'})
        self.client.login(username='cmviewer', password='pw12345678')
        r = self.client.get(self._u('editor_comment_counts'))
        self.assertIn('survey:all', r.json()['new'])


class EmptySessionCommentLabelTest(_EmptySessionFixture):
    """Comment anchors number responses the way the table does."""

    def test_labels_follow_response_numbers(self):
        """
        GIVEN sessions A (answered), B (empty), C (answered)
        WHEN their comment anchor labels are built
        THEN A is Response #1, C is Response #2 and B is a response without answers
        """
        from survey.comments import session_label
        a = self._session()
        b = self._session(answered=False)
        c = self._session()
        self.assertEqual(session_label(self.survey, a, a.id), 'Response #1')
        self.assertEqual(session_label(self.survey, c, c.id), 'Response #2')
        self.assertEqual(session_label(self.survey, b, b.id), 'Response without answers')
