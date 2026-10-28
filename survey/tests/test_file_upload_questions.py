"""Tests for the `file-upload-questions` capability (openspec/specs/file-upload-questions/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from io import BytesIO
import json
import re
import zipfile
from survey.models import Organization, SurveyHeader, SurveySection, Question, SurveySession, Answer, Membership, SurveyCollaborator, PublicResultsPage
from io import StringIO
from django.core.management import call_command


class UploadModelTest(TestCase):
    """The Upload row: the owner of respondent bytes before an Answer claims them."""

    def setUp(self):
        org = Organization.objects.create(name="Upload Org")
        self.survey = SurveyHeader.objects.create(name="upload_survey", organization=org, redirect_url="#")
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="sec1", code="S1",
        )
        self.question = Question.objects.create(
            survey_section=self.section, name="Site photo", code="Q_PHOTO",
            input_type="photo",
        )
        self.session = SurveySession.objects.create(survey=self.survey)

    def _upload(self, name='shot.jpg'):
        from django.core.files.base import ContentFile
        from survey.models import Upload

        return Upload.objects.create(
            session=self.session, question=self.question,
            file=ContentFile(b'jpegbytes', name=name),
            original_name=name, content_type='image/jpeg', size=9,
        )

    def test_round_trip_stores_under_survey_and_token(self):
        """
        GIVEN a fresh upload on filesystem storage
        WHEN it is saved
        THEN the key nests under the survey uuid and its own token, keeping the name
        """
        up = self._upload()

        self.assertIn(str(self.survey.uuid), up.file.name)
        self.assertIn(str(up.token), up.file.name)
        self.assertTrue(up.file.name.endswith('shot.jpg'))
        self.assertFalse(up.attached)

    def test_deleting_the_row_deletes_the_file(self):
        """
        GIVEN a stored upload
        WHEN its row is deleted
        THEN the stored file is gone too — reclamation must not leak objects
        """
        up = self._upload()
        storage, name = up.file.storage, up.file.name
        self.assertTrue(storage.exists(name))

        up.delete()

        self.assertFalse(storage.exists(name))

    def test_session_cascade_takes_uploads_and_files(self):
        """
        GIVEN an upload owned by a session
        WHEN the session is deleted
        THEN the upload row and its file follow
        """
        from survey.models import Upload

        up = self._upload()
        storage, name = up.file.storage, up.file.name

        self.session.delete()

        self.assertFalse(Upload.objects.filter(token=up.token).exists())
        self.assertFalse(storage.exists(name))

    def test_attached_upload_survives_answer_deletion(self):
        """
        GIVEN an answer holding an upload
        WHEN the answer is deleted
        THEN SET_NULL leaves the upload row (its lifecycle belongs to the session)
        """
        from survey.models import Upload

        up = self._upload()
        up.attached = True
        up.save(update_fields=['attached'])
        answer = Answer.objects.create(
            survey_session=self.session, question=self.question, upload=up,
        )

        answer.delete()

        self.assertTrue(Upload.objects.filter(token=up.token).exists())


@override_settings(FILE_UPLOAD_QUESTIONS=True)
class SurveyUploadEndpointTest(TestCase):
    """The async upload endpoint — the only route that accepts respondent bytes."""

    def setUp(self):
        org = Organization.objects.create(name="Up Org")
        self.survey = SurveyHeader.objects.create(
            name="upload_ep_survey", organization=org, redirect_url="#", status="published",
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="sec1", code="S1",
        )
        self.photo_q = Question.objects.create(
            survey_section=self.section, name="Photo", code="Q_PH", input_type="photo",
        )
        self.audio_q = Question.objects.create(
            survey_section=self.section, name="Voice", code="Q_AU", input_type="audio",
        )
        self.doc_q = Question.objects.create(
            survey_section=self.section, name="Doc", code="Q_DOC", input_type="document",
        )
        self.url = f'/surveys/{self.survey.uuid}/upload/'

    def _open_session(self):
        self.client.get(f'/surveys/{self.survey.uuid}/sec1/')

    def _post(self, question_code, name, content, content_type):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return self.client.post(self.url, {
            'question': question_code,
            'file': SimpleUploadedFile(name, content, content_type=content_type),
        })

    JPEG = b'\xff\xd8\xff\xe0' + b'0' * 32
    PDF = b'%PDF-1.4 ' + b'0' * 32

    def test_photo_audio_document_happy_paths(self):
        """
        GIVEN an open session on a published survey
        WHEN each file type uploads a matching file
        THEN a token comes back and an Upload row exists
        """
        from survey.models import Upload

        self._open_session()
        cases = [
            (self.photo_q, 'a.jpg', self.JPEG, 'image/jpeg'),
            (self.audio_q, 'v.webm', b'\x1aE\xdf\xa3rec', 'audio/webm'),
            (self.doc_q, 'r.pdf', self.PDF, 'application/pdf'),
        ]
        for question, name, content, ctype in cases:
            response = self._post(question.code, name, content, ctype)
            self.assertEqual(response.status_code, 200, response.content)
            token = response.json()['token']
            self.assertTrue(Upload.objects.filter(token=token, question=question).exists())

    def test_svg_is_rejected_for_photo(self):
        """
        GIVEN the stored-XSS classic
        WHEN an SVG is uploaded to a photo question
        THEN it is refused and nothing is stored
        """
        from survey.models import Upload

        self._open_session()
        response = self._post('Q_PH', 'x.svg', b'<svg onload=alert(1)>', 'image/svg+xml')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'type_not_allowed')
        self.assertEqual(Upload.objects.count(), 0)

    def test_mislabelled_pdf_is_caught_by_magic_bytes(self):
        """
        GIVEN a file claiming application/pdf whose bytes are not a PDF
        WHEN it is uploaded
        THEN the magic-byte check refuses it
        """
        self._open_session()
        response = self._post('Q_DOC', 'fake.pdf', b'MZ\x90\x00 not a pdf', 'application/pdf')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'content_mismatch')

    def test_platform_size_cap(self):
        """
        GIVEN a file over the platform cap
        WHEN it is uploaded
        THEN it is refused as too large
        """
        from survey import uploads as up

        self._open_session()
        big = self.JPEG + b'0' * (up.PLATFORM_MAX_BYTES)
        response = self._post('Q_PH', 'big.jpg', big, 'image/jpeg')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'too_large')

    def test_session_file_count_cap(self):
        """
        GIVEN a session at the per-session file cap
        WHEN one more upload arrives
        THEN it is refused
        """
        from django.core.files.base import ContentFile
        from survey import uploads as up
        from survey.models import Upload

        self._open_session()
        session = SurveySession.objects.get(survey=self.survey)
        for i in range(up.SESSION_MAX_FILES):
            Upload.objects.create(
                session=session, question=self.photo_q,
                file=ContentFile(b'x', name=f'f{i}.jpg'),
                original_name=f'f{i}.jpg', content_type='image/jpeg', size=1,
            )

        response = self._post('Q_PH', 'one-more.jpg', self.JPEG, 'image/jpeg')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'session_file_cap')

    def test_no_session_is_forbidden(self):
        """
        GIVEN no survey session (the survey was never opened)
        WHEN an upload arrives
        THEN 403 — the endpoint is not anonymous storage
        """
        response = self._post('Q_PH', 'a.jpg', self.JPEG, 'image/jpeg')

        self.assertEqual(response.status_code, 403)

    def test_non_file_question_is_refused(self):
        """
        GIVEN a text question's code
        WHEN a file is posted for it
        THEN the endpoint refuses — only file types accept bytes
        """
        Question.objects.create(
            survey_section=self.section, name="T", code="Q_TXT", input_type="text",
        )
        self._open_session()
        response = self._post('Q_TXT', 'a.jpg', self.JPEG, 'image/jpeg')

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error'], 'unknown_question')

    @override_settings(FILE_UPLOAD_QUESTIONS=False)
    def test_kill_switch_hides_the_endpoint(self):
        """
        GIVEN the kill switch off
        WHEN an upload arrives
        THEN 404 — the endpoint does not exist for the outside world
        """
        self._open_session()
        response = self._post('Q_PH', 'a.jpg', self.JPEG, 'image/jpeg')

        self.assertEqual(response.status_code, 404)


@override_settings(FILE_UPLOAD_QUESTIONS=True)
class FileAnswerAttachmentTest(TestCase):
    """Token resolution at section submit — where uploads become answers."""

    JPEG = b'\xff\xd8\xff\xe0' + b'0' * 16

    def setUp(self):
        org = Organization.objects.create(name="Attach Org")
        self.survey = SurveyHeader.objects.create(
            name="attach_survey", organization=org, redirect_url="#", status="published",
        )
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="sec1", code="S1",
        )
        self.photo_q = Question.objects.create(
            survey_section=self.section, name="Photo", code="Q_PH", input_type="photo",
        )
        self.text_q = Question.objects.create(
            survey_section=self.section, name="Note", code="Q_TXT", input_type="text",
        )
        self.section_url = f'/surveys/{self.survey.uuid}/sec1/'

    def _upload_token(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.get(self.section_url)
        response = self.client.post(f'/surveys/{self.survey.uuid}/upload/', {
            'question': 'Q_PH',
            'file': SimpleUploadedFile('site.jpg', self.JPEG, content_type='image/jpeg'),
        })
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()['token']

    def test_submit_attaches_the_upload(self):
        """
        GIVEN an uploaded file's token in the section POST
        WHEN the section is submitted
        THEN the answer references the upload and the upload is attached
        """
        from survey.models import Upload

        token = self._upload_token()
        self.client.post(self.section_url, {'Q_PH': token, 'Q_TXT': 'note'})

        answer = Answer.objects.get(question=self.photo_q)
        self.assertEqual(str(answer.upload_id), token)
        self.assertTrue(Upload.objects.get(token=token).attached)

    def test_foreign_token_is_skipped_but_section_saves(self):
        """
        GIVEN a token that belongs to another session
        WHEN the section is submitted with it
        THEN no file answer appears, the text answer still saves
        """
        token = self._upload_token()
        # Второй клиент = другая сессия респондента.
        from django.test import Client

        other = Client()
        other.get(self.section_url)
        other.post(self.section_url, {'Q_PH': token, 'Q_TXT': 'stolen'})

        other_session = SurveySession.objects.exclude(
            id=self.client.session['survey_session_id']).get()
        self.assertFalse(Answer.objects.filter(
            survey_session=other_session, question=self.photo_q).exists())
        self.assertTrue(Answer.objects.filter(
            survey_session=other_session, question=self.text_q, text='stolen').exists())

    def test_resubmit_keeps_the_file_without_reupload(self):
        """
        GIVEN a submitted file answer
        WHEN the section is resubmitted with the same token
        THEN the same upload stays attached and no duplicate exists
        """
        from survey.models import Upload

        token = self._upload_token()
        self.client.post(self.section_url, {'Q_PH': token, 'Q_TXT': 'v1'})
        self.client.post(self.section_url, {'Q_PH': token, 'Q_TXT': 'v2'})

        self.assertEqual(Upload.objects.count(), 1)
        answer = Answer.objects.get(question=self.photo_q)
        self.assertEqual(str(answer.upload_id), token)
        self.assertTrue(Upload.objects.get(token=token).attached)

    def test_replacing_detaches_the_old_upload(self):
        """
        GIVEN a submitted file answer
        WHEN the section is resubmitted with a different token
        THEN the old upload is detached for reclamation, the new one attached
        """
        from survey.models import Upload

        first = self._upload_token()
        self.client.post(self.section_url, {'Q_PH': first, 'Q_TXT': 'x'})
        second = self._upload_token()
        self.client.post(self.section_url, {'Q_PH': second, 'Q_TXT': 'x'})

        self.assertFalse(Upload.objects.get(token=first).attached)
        self.assertTrue(Upload.objects.get(token=second).attached)

    def test_prepopulation_carries_the_token(self):
        """
        GIVEN a submitted file answer
        WHEN the section is revisited
        THEN the rendered form carries the token in the hidden input
        """
        token = self._upload_token()
        self.client.post(self.section_url, {'Q_PH': token, 'Q_TXT': 'x'})

        response = self.client.get(self.section_url)

        self.assertContains(response, token)
        self.assertContains(response, 'site.jpg')

    def test_required_renders_the_client_side_guard(self):
        """
        GIVEN a required photo question
        WHEN the section renders
        THEN the widget carries the data-required marker its JS submit-guard
        keys on — required is client-enforced platform-wide (the section POST
        never calls form.is_valid()), and a hidden input gets no HTML5
        validation, so the widget must do the blocking itself
        """
        self.photo_q.required = True
        self.photo_q.save(update_fields=['required'])

        response = self.client.get(self.section_url)

        self.assertContains(response, 'data-required')

    def test_absent_token_stores_no_answer_and_breaks_nothing(self):
        """
        GIVEN a required photo question and a POST with no token (JS bypassed)
        WHEN the section is submitted
        THEN no file answer exists and the other answers save — consistent
        with how every other required type behaves against a bare POST
        """
        self.photo_q.required = True
        self.photo_q.save(update_fields=['required'])
        self.client.get(self.section_url)

        self.client.post(self.section_url, {'Q_TXT': 'only text'})

        self.assertFalse(Answer.objects.filter(question=self.photo_q).exists())
        self.assertTrue(Answer.objects.filter(question=self.text_q, text='only text').exists())

    @override_settings(FILE_UPLOAD_QUESTIONS=False)
    def test_kill_switch_drops_the_question_but_not_the_section(self):
        """
        GIVEN the switch off and a stored file question
        WHEN a respondent opens and submits the section
        THEN no upload widget renders and the other answers save
        """
        response = self.client.get(self.section_url)
        self.assertNotContains(response, 'data-file-upload')

        self.client.post(self.section_url, {'Q_TXT': 'works'})
        self.assertTrue(Answer.objects.filter(question=self.text_q, text='works').exists())


class FilePickerGroupTest(TestCase):
    """The Files group in the question type picker, and its kill switch."""

    def setUp(self):
        self.user = User.objects.create_user(username='fpicker', password='pass')
        self.org = Organization.objects.create(name="Picker Org")
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name="picker_survey", organization=self.org, created_by=self.user, redirect_url="#",
        )
        SurveyCollaborator.objects.create(user=self.user, survey=self.survey, role='owner')
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="sec1", code="S1",
        )
        self.client.login(username='fpicker', password='pass')

    @override_settings(FILE_UPLOAD_QUESTIONS=True)
    def test_switch_on_offers_the_files_group(self):
        """
        GIVEN the switch on
        WHEN picker groups are built from the form's choices
        THEN a Files group holds exactly photo, audio, document
        """
        from survey.editor_forms import QuestionForm
        from survey.question_types import picker_groups_for

        form = QuestionForm(section=self.section)
        groups = dict(picker_groups_for(list(form.fields['input_type'].choices)))

        self.assertIn('Files', groups)
        self.assertEqual({t['value'] for t in groups['Files']},
                         {'photo', 'audio', 'document'})

    @override_settings(FILE_UPLOAD_QUESTIONS=False)
    def test_switch_off_hides_group_and_rejects_the_type(self):
        """
        GIVEN the switch off
        WHEN the form is built and a photo type is submitted anyway
        THEN no Files group exists and the type is an invalid choice
        """
        from survey.editor_forms import QuestionForm
        from survey.question_types import picker_groups_for

        form = QuestionForm(section=self.section)
        groups = dict(picker_groups_for(list(form.fields['input_type'].choices)))
        self.assertNotIn('Files', groups)

        bound = QuestionForm(data={'name': 'X', 'input_type': 'photo'}, section=self.section)
        self.assertFalse(bound.is_valid())
        self.assertIn('input_type', bound.errors)

    @override_settings(FILE_UPLOAD_QUESTIONS=True)
    def test_file_types_are_offered_to_subquestions(self):
        """
        GIVEN a geo question's sub-question dialog
        WHEN its type choices are built
        THEN photo is among them — the field-collection scenario depends on it
        """
        from survey.editor_forms import QuestionForm

        form = QuestionForm(section=self.section, is_subquestion=True)
        values = {v for v, _ in form.fields['input_type'].choices}

        self.assertIn('photo', values)
        self.assertNotIn('point', values)


@override_settings(FILE_UPLOAD_QUESTIONS=True)
class FileQuestionEditorSmokeTest(TestCase):
    """Creating each file type through the editor's real create endpoint."""

    def setUp(self):
        self.user = User.objects.create_user(username='fedit', password='pass')
        self.org = Organization.objects.create(name="FEdit Org")
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name="fedit_survey", organization=self.org, created_by=self.user, redirect_url="#",
        )
        SurveyCollaborator.objects.create(user=self.user, survey=self.survey, role='owner')
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="sec1", code="S1",
        )
        self.client.login(username='fedit', password='pass')
        self.url = f'/editor/surveys/{self.survey.uuid}/sections/{self.section.id}/questions/new/'

    def test_each_file_type_creates_and_renders_for_respondents(self):
        """
        GIVEN the editor create endpoint
        WHEN each file type is created and the respondent section is opened
        THEN the question exists and the upload widget renders
        """
        for input_type in ('photo', 'audio', 'document'):
            response = self.client.post(self.url, {
                'name': f'{input_type} q', 'input_type': input_type, 'color': '#000000',
            })
            self.assertEqual(response.status_code, 200, response.content[:300])
            self.assertTrue(Question.objects.filter(
                survey_section=self.section, input_type=input_type).exists())

        self.survey.status = 'published'
        self.survey.save(update_fields=['status'])
        page = self.client.get(f'/surveys/{self.survey.uuid}/sec1/')
        self.assertContains(page, 'data-file-upload', count=3)
        self.assertContains(page, 'capture="environment"', count=1)
        self.assertContains(page, 'data-recorder="1"', count=1)

    def test_creator_cap_is_stored_clamped(self):
        """
        GIVEN a creator cap above the platform ceiling
        WHEN the question is saved with vs_max_file_mb=100
        THEN the stored cap is clamped to the platform maximum
        """
        from survey.uploads import PLATFORM_MAX_BYTES

        # Лимиты сохраняются уже при СОЗДАНИИ — автор, выставивший их в
        # диалоге, не обязан открывать вопрос второй раз.
        self.client.post(self.url, {
            'name': 'photo capped', 'input_type': 'photo', 'color': '#000000',
            'vs_max_file_mb': '100', 'vs_max_files': '99',
        })

        question = Question.objects.get(survey_section=self.section)
        self.assertEqual(question.validation_settings.get('max_file_bytes'), PLATFORM_MAX_BYTES)
        from survey.uploads import PLATFORM_MAX_FILES
        self.assertEqual(question.validation_settings.get('max_files'), PLATFORM_MAX_FILES)


class ReclaimOrphanUploadsTest(TestCase):
    """Orphan reclamation: unattached and stale goes, everything else stays."""

    def setUp(self):
        org = Organization.objects.create(name="Reclaim Org")
        self.survey = SurveyHeader.objects.create(name="reclaim_survey", organization=org, redirect_url="#")
        section = SurveySection.objects.create(survey_header=self.survey, name="sec1", code="S1")
        self.question = Question.objects.create(
            survey_section=section, name="P", code="Q_P", input_type="photo",
        )
        self.session = SurveySession.objects.create(survey=self.survey)

    def _upload(self, attached=False, age_hours=0):
        from datetime import timedelta

        from django.core.files.base import ContentFile
        from django.utils import timezone as tz
        from survey.models import Upload

        up = Upload.objects.create(
            session=self.session, question=self.question,
            file=ContentFile(b'x', name='f.jpg'),
            original_name='f.jpg', content_type='image/jpeg', size=1,
            attached=attached,
        )
        if age_hours:
            Upload.objects.filter(token=up.token).update(
                created_at=tz.now() - timedelta(hours=age_hours))
        return up

    def _run(self, *args):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command('reclaim_orphan_uploads', *args, stdout=out)
        return out.getvalue()

    def test_stale_orphan_is_deleted_with_its_file(self):
        """
        GIVEN an unattached upload past the grace period
        WHEN reclamation runs with --delete
        THEN the row and the stored file are gone
        """
        from survey.models import Upload

        up = self._upload(age_hours=72)
        storage, name = up.file.storage, up.file.name

        output = self._run('--delete')

        self.assertIn('Reclaimed 1', output)
        self.assertFalse(Upload.objects.exists())
        self.assertFalse(storage.exists(name))

    def test_fresh_orphan_and_attached_survive(self):
        """
        GIVEN a fresh orphan and a stale attached upload
        WHEN reclamation runs with --delete
        THEN both survive — grace period and attachment each protect
        """
        from survey.models import Upload

        self._upload(age_hours=1)
        self._upload(attached=True, age_hours=500)

        self._run('--delete')

        self.assertEqual(Upload.objects.count(), 2)

    def test_dry_run_touches_nothing(self):
        """
        GIVEN a stale orphan
        WHEN reclamation runs without --delete
        THEN it only reports
        """
        from survey.models import Upload

        self._upload(age_hours=72)

        output = self._run()

        self.assertIn('would delete 1', output)
        self.assertEqual(Upload.objects.count(), 1)


@override_settings(FILE_UPLOAD_QUESTIONS=True)
class FileAnswersCreatorSurfacesTest(TestCase):
    """Where creators meet respondent files: table, modal payloads, ZIP, and
    the surface that must never show them — public results."""

    JPEG = b'\xff\xd8\xff\xe0' + b'0' * 16

    def setUp(self):
        self.user = User.objects.create_user(username='fcreator', password='pass')
        self.org = Organization.objects.create(name="FC Org")
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name="fc_survey", organization=self.org, created_by=self.user,
            redirect_url="#", status="published",
        )
        SurveyCollaborator.objects.create(user=self.user, survey=self.survey, role='owner')
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="sec1", code="S1",
        )
        self.photo_q = Question.objects.create(
            survey_section=self.section, name="Evidence", code="Q_PH", input_type="photo",
        )
        # Респондентский цикл: сессия, загрузка, сабмит
        self.client.get(f'/surveys/{self.survey.uuid}/sec1/')
        from django.core.files.uploadedfile import SimpleUploadedFile

        up_response = self.client.post(f'/surveys/{self.survey.uuid}/upload/', {
            'question': 'Q_PH',
            'file': SimpleUploadedFile('street scene.jpg', self.JPEG, content_type='image/jpeg'),
        })
        self.token = up_response.json()['token']
        self.client.post(f'/surveys/{self.survey.uuid}/sec1/', {'Q_PH': self.token})
        self.session = SurveySession.objects.get(survey=self.survey)
        self.client.login(username='fcreator', password='pass')

    def test_responses_table_links_the_filename(self):
        """
        GIVEN a submitted file answer
        WHEN the creator opens the responses table
        THEN the filename appears wrapped in a link to the stored file
        """
        response = self.client.get(f'/editor/surveys/{self.survey.uuid}/analytics/table/')

        self.assertContains(response, 'street scene.jpg')
        content = response.content.decode()
        import re
        self.assertTrue(re.search(r'<a href="[^"]+"[^>]*>street scene.jpg</a>', content),
                        'filename is not a link')

    def test_session_detail_previews_by_type(self):
        """
        GIVEN submitted photo and audio answers
        WHEN the session detail modal renders
        THEN the photo shows as an inline thumbnail and the audio as a player,
        both sourced from server-minted URLs
        """
        from django.core.files.uploadedfile import SimpleUploadedFile

        audio_q = Question.objects.create(
            survey_section=self.section, name="Voice", code="Q_AU", input_type="audio",
        )
        self.client.logout()
        self.client.get(f'/surveys/{self.survey.uuid}/sec1/')
        up = self.client.post(f'/surveys/{self.survey.uuid}/upload/', {
            'question': 'Q_AU',
            'file': SimpleUploadedFile('rec.webm', b'\x1aE\xdf\xa3xx', content_type='audio/webm'),
        })
        audio_token = up.json()['token']
        self.client.post(f'/surveys/{self.survey.uuid}/sec1/', {'Q_AU': audio_token})
        audio_session = SurveySession.objects.exclude(id=self.session.id).latest('id')
        self.client.login(username='fcreator', password='pass')

        photo_page = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/analytics/sessions/{self.session.id}/')
        audio_page = self.client.get(
            f'/editor/surveys/{self.survey.uuid}/analytics/sessions/{audio_session.id}/')

        self.assertContains(photo_page, '<img', msg_prefix='photo thumbnail missing')
        self.assertContains(photo_page, 'street scene.jpg')
        self.assertContains(audio_page, '<audio', msg_prefix='audio player missing')
        self.assertContains(audio_page, 'rec.webm')

    def test_zip_contains_the_file_and_the_cell_names_it(self):
        """
        GIVEN a submitted file answer
        WHEN the creator downloads survey data
        THEN the archive holds the file under files/<sid>/ and the CSV cell
        carries exactly that path
        """
        response = self.client.get(f'/surveys/{self.survey.uuid}/download')
        self.assertEqual(response.status_code, 200)

        archive = zipfile.ZipFile(BytesIO(response.content))
        names = archive.namelist()
        file_entries = [n for n in names if n.startswith('files/')]
        self.assertEqual(len(file_entries), 1)
        expected = f'files/{self.session.id}/Q_PH__street scene.jpg'
        self.assertEqual(file_entries[0], expected)
        self.assertEqual(archive.read(expected), self.JPEG)

        csv_name = [n for n in names if n.endswith('.csv')][0]
        self.assertIn(expected, archive.read(csv_name).decode())

    def test_public_results_never_see_uploads(self):
        """
        GIVEN a survey with file answers and a public results page
        WHEN the page data is rendered
        THEN neither the filename nor any upload path appears anywhere in it
        """
        from survey.models import PublicResultsPage
        from survey.public_results import PublicResultsService, render_page_data

        page = PublicResultsPage.objects.create(survey=self.survey, slug='fc-results')
        data = render_page_data(page)

        blob = json.dumps(data, default=str)
        self.assertNotIn('street scene.jpg', blob)
        self.assertNotIn('files/', blob)
        self.assertNotIn('uploads/', blob)


@override_settings(FILE_UPLOAD_QUESTIONS=True)
class MultiFileAndPreviewUploadTest(TestCase):
    """Several files per question, and uploads from the editor's Live Preview."""

    JPEG = b'\xff\xd8\xff\xe0' + b'0' * 16

    def setUp(self):
        self.user = User.objects.create_user(username='multi', password='pass')
        self.org = Organization.objects.create(name="Multi Org")
        Membership.objects.create(user=self.user, organization=self.org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name="multi_survey", organization=self.org, created_by=self.user,
            redirect_url="#", status="published",
        )
        SurveyCollaborator.objects.create(user=self.user, survey=self.survey, role='owner')
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="sec1", code="S1",
        )
        self.photo_q = Question.objects.create(
            survey_section=self.section, name="Photos", code="Q_PH", input_type="photo",
        )
        self.section_url = f'/surveys/{self.survey.uuid}/sec1/'
        self.upload_url = f'/surveys/{self.survey.uuid}/upload/'

    def _upload(self, name):
        from django.core.files.uploadedfile import SimpleUploadedFile

        response = self.client.post(self.upload_url, {
            'question': 'Q_PH',
            'file': SimpleUploadedFile(name, self.JPEG, content_type='image/jpeg'),
        })
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()['token']

    def test_three_photos_become_three_answers(self):
        """
        GIVEN three uploaded photos on one question (default photo cap is 5)
        WHEN the section is submitted with all three tokens
        THEN three answers exist, each holding its own upload
        """
        self.client.get(self.section_url)
        tokens = [self._upload(f'p{i}.jpg') for i in range(3)]

        self.client.post(self.section_url, {'Q_PH': tokens})

        answers = Answer.objects.filter(question=self.photo_q)
        self.assertEqual(answers.count(), 3)
        self.assertEqual({str(a.upload_id) for a in answers}, set(tokens))

    def test_the_cap_clamps_extra_tokens(self):
        """
        GIVEN a question capped at 2 files
        WHEN the section is submitted with three valid tokens
        THEN only the first two attach
        """
        self.photo_q.validation_settings = {'max_files': 2}
        self.photo_q.save(update_fields=['validation_settings'])
        self.client.get(self.section_url)
        tokens = [self._upload(f'p{i}.jpg') for i in range(3)]

        self.client.post(self.section_url, {'Q_PH': tokens})

        answers = Answer.objects.filter(question=self.photo_q)
        self.assertEqual(answers.count(), 2)
        self.assertEqual({str(a.upload_id) for a in answers}, set(tokens[:2]))

    def test_prepopulation_returns_every_token(self):
        """
        GIVEN two submitted photos
        WHEN the section re-renders
        THEN both tokens are present as hidden inputs
        """
        self.client.get(self.section_url)
        tokens = [self._upload(f'p{i}.jpg') for i in range(2)]
        self.client.post(self.section_url, {'Q_PH': tokens})

        response = self.client.get(self.section_url)

        for token in tokens:
            self.assertContains(response, token)

    def test_collaborator_uploads_from_preview_without_a_session(self):
        """
        GIVEN the editor's Live Preview (no respondent session, authed owner)
        WHEN a file is uploaded
        THEN it succeeds against a lazily-created session tagged editor-preview

        On mobile the preview IS how creators test — a 403 here made the
        feature look broken to its own author.
        """
        self.client.login(username='multi', password='pass')

        token = self._upload('preview.jpg')

        from survey.models import Upload
        upload = Upload.objects.get(token=token)
        self.assertEqual(upload.session.tags, ['editor-preview'])
        # повторная загрузка переиспользует ту же сессию
        self._upload('preview2.jpg')
        self.assertEqual(
            SurveySession.objects.filter(survey=self.survey,
                                         tags__contains=['editor-preview']).count(), 1)

    def test_anonymous_without_session_still_forbidden(self):
        """
        GIVEN no session and no authenticated user
        WHEN a file is uploaded
        THEN 403 — the abuse posture is unchanged for the world at large
        """
        from django.core.files.uploadedfile import SimpleUploadedFile

        response = self.client.post(self.upload_url, {
            'question': 'Q_PH',
            'file': SimpleUploadedFile('x.jpg', self.JPEG, content_type='image/jpeg'),
        })

        self.assertEqual(response.status_code, 403)


@override_settings(FILE_UPLOAD_QUESTIONS=True)
class MultiFileExportTest(TestCase):
    """Export with several files: every path in the cell, every file in the ZIP,
    including photos attached to a mapped point."""

    JPEG = b'\xff\xd8\xff\xe0' + b'0' * 16

    def setUp(self):
        self.user = User.objects.create_user(username='mexp', password='pass')
        org = Organization.objects.create(name="MExp Org")
        Membership.objects.create(user=self.user, organization=org, role='owner')
        self.survey = SurveyHeader.objects.create(
            name="mexp_survey", organization=org, created_by=self.user,
            redirect_url="#", status="published",
        )
        SurveyCollaborator.objects.create(user=self.user, survey=self.survey, role='owner')
        self.section = SurveySection.objects.create(
            survey_header=self.survey, name="sec1", code="S1",
        )
        self.photo_q = Question.objects.create(
            survey_section=self.section, name="Photos", code="Q_PH", input_type="photo",
        )
        self.point_q = Question.objects.create(
            survey_section=self.section, name="Spot", code="Q_SPOT", input_type="point",
        )
        self.sub_photo = Question.objects.create(
            survey_section=self.section, name="Spot photo", code="Q_SPOT_PH",
            input_type="photo", parent_question_id=self.point_q,
        )

    def _upload(self, code, name):
        from django.core.files.uploadedfile import SimpleUploadedFile

        response = self.client.post(f'/surveys/{self.survey.uuid}/upload/', {
            'question': code,
            'file': SimpleUploadedFile(name, self.JPEG, content_type='image/jpeg'),
        })
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()['token']

    def test_multi_file_cells_and_zip_cover_every_file(self):
        """
        GIVEN two photos on a section question and two on a point's sub-question
        WHEN the creator downloads survey data
        THEN the CSV cell and the GeoJSON property list BOTH paths each,
        and all four files are present in the archive
        """
        section_url = f'/surveys/{self.survey.uuid}/sec1/'
        self.client.get(section_url)
        top = [self._upload('Q_PH', f'top{i}.jpg') for i in range(2)]
        sub = [self._upload('Q_SPOT_PH', f'spot{i}.jpg') for i in range(2)]
        geojson_str = json.dumps({
            'type': 'Feature',
            'geometry': {'type': 'Point', 'coordinates': [74.6, 42.87]},
            'properties': {'question_id': 'Q_SPOT', 'Q_SPOT_PH': sub},
        })
        self.client.post(section_url, {'Q_PH': top, 'Q_SPOT': geojson_str})
        session = SurveySession.objects.get(survey=self.survey)

        self.client.login(username='mexp', password='pass')
        response = self.client.get(f'/surveys/{self.survey.uuid}/download')
        archive = zipfile.ZipFile(BytesIO(response.content))
        names = archive.namelist()

        file_entries = sorted(n for n in names if n.startswith('files/'))
        self.assertEqual(len(file_entries), 4, file_entries)

        csv_text = archive.read([n for n in names if n.endswith('.csv')][0]).decode()
        for i in range(2):
            self.assertIn(f'files/{session.id}/Q_PH__top{i}.jpg', csv_text)

        geojson_text = archive.read(
            [n for n in names if n.endswith('.geojson')][0]).decode()
        for i in range(2):
            self.assertIn(f'files/{session.id}/Q_SPOT_PH__spot{i}.jpg', geojson_text)
