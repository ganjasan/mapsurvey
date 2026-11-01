"""Tests for the `paper-photo-entry` capability (openspec/changes/paper-photo-entry/specs/paper-photo-entry/spec.md).

Change paper-photo-entry (#495, epic #350 item 3): photos or scans of filled paper forms become
paper responses the operator checks beside the picture. The model is a fake provider; the code path
is real — forms printed by `build_form` (with and without copy numbers) are rendered to pixels with
pypdfium2 and read back with zxing-cpp, which is ingest + code + placement end to end, offline.
"""
import io
import json
import uuid
from contextlib import contextmanager
from unittest import mock

from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from billing.tests.helpers import make_sub
from survey.ai.client import ProviderError
from survey.models import (
    AIGenerationEvent, Answer, Membership, Organization, PaperPage, PaperSheet, PaperUpload, PrintedForm, Question,
    SurveyHeader, SurveySection, SurveySession,
)
from survey.paper import extract, marks, sheets as sheets_mod
from survey.paper.ingest import ingest_upload, sniff
from survey.tests.helpers import _FakeProvider


def _jpeg(width=400, height=560, color=(255, 255, 255)):
    buf = io.BytesIO()
    Image.new('RGB', (width, height), color).save(buf, format='JPEG')
    return buf.getvalue()


def _field(value, confidence=0.95, unreadable=False):
    return {'value': value, 'confidence': confidence, 'unreadable': unreadable}


def _pdf_page_jpegs(pdf_bytes, indexes):
    """Pages of a printed PDF as phone-photo stand-ins (JPEG at 200 dpi)."""
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(pdf_bytes)
    out = []
    for i in indexes:
        img = doc[i].render(scale=200 / 72).to_pil()
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=90)
        out.append(buf.getvalue())
    doc.close()
    return out


@contextmanager
def _eager_tasks():
    """The views enqueue Celery tasks; the suite has no broker, so `.delay` runs the task."""
    from survey import tasks

    def read_now(batch_id):
        # The worker waits for the uploads to settle; a test has no clock to wait on.
        for pk in list(PaperPage.objects.filter(batch_id=batch_id, status='queued', sheet__isnull=False)
                       .order_by('sheet__seq', 'page_number', 'seq').values_list('pk', flat=True)):
            tasks.recognise_paper_page(pk)
    with mock.patch.object(tasks.ingest_paper_upload, 'delay', side_effect=lambda pk: tasks.ingest_paper_upload(pk)), \
            mock.patch.object(tasks.recognise_paper_page, 'delay', side_effect=lambda pk: tasks.recognise_paper_page(pk)), \
            mock.patch.object(tasks.delete_sheet_images, 'delay', side_effect=lambda pk: tasks.delete_sheet_images(pk)), \
            mock.patch.object(tasks, 'schedule_reading', side_effect=read_now):
        yield


def _png(width, height, color=(200, 220, 240)):
    buf = io.BytesIO()
    Image.new('RGB', (width, height), color).save(buf, format='PNG')
    return buf.getvalue()


def _response(status=200, content=b''):
    response = mock.Mock()
    response.status_code = status
    response.content = content
    return response


def _blank_provider(n=20):
    """A provider that reads nothing on any page — for tests about placement, not answers."""
    return _FakeProvider([{'fields': []} for _ in range(n)])


class _PaperFixture(TestCase):
    """A Pro workspace, a two-section survey (choice + text + multichoice, then a point)."""

    def setUp(self):
        cache.clear()
        self.org = Organization.objects.create(name='Paper Org', slug='paper-org')
        self.owner = User.objects.create_user('paper_owner', password='pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        self.sub = make_sub(self.org)
        self.survey = SurveyHeader.objects.create(
            name='Paper survey', organization=self.org, created_by=self.owner, status='published',
            redirect_url='#', available_languages=['en', 'pl'], version_number=1)
        self.s1 = SurveySection.objects.create(
            survey_header=self.survey, name='about', title='About', code='S1', is_head=True, layout='form')
        self.s2 = SurveySection.objects.create(
            survey_header=self.survey, name='where', title='Where', code='S2', prev_section=self.s1,
            start_map_postion=Point(13.4, 52.5), start_map_zoom=13)
        self.s1.next_section = self.s2
        self.s1.save()
        self.alb = Question.objects.create(
            survey_section=self.s1, code='ALB', name='Albino?', input_type='choice', order_number=1, required=True,
            choices=[{'code': 1, 'name': {'en': 'Yes', 'pl': 'Tak'}}, {'code': 0, 'name': {'en': 'No', 'pl': 'Nie'}}])
        self.why = Question.objects.create(
            survey_section=self.s1, code='WHY', name='Why?', input_type='text', order_number=2)
        self.mood = Question.objects.create(
            survey_section=self.s1, code='MOOD', name='Mood', input_type='multichoice', order_number=3,
            choices=[{'code': 1, 'name': 'Good'}, {'code': 2, 'name': 'Other', 'other': True}])
        self.where = Question.objects.create(
            survey_section=self.s2, code='WHERE', name='Where?', input_type='point', order_number=1)
        self.login(self.owner)

    def login(self, user):
        self.client.force_login(user)
        s = self.client.session
        s['active_org_id'] = self.org.id
        s.save()

    def url(self, name, *args):
        return reverse(name, args=[self.survey.uuid, *args])

    def print_single(self):
        from survey.print.pdf import build_form
        with override_settings(MAPBOX_ACCESS_TOKEN=''):
            return build_form(self.survey, 'en', 'a4', user=self.owner, base_url='https://example.test')

    def print_copies(self, n):
        from survey.print.pdf import print_copies
        with override_settings(MAPBOX_ACCESS_TOKEN=''):
            return print_copies(self.survey, 'en', 'a4', n, user=self.owner, base_url='https://example.test')

    @property
    def inbox(self):
        return sheets_mod.inbox_for(self.survey, user=self.owner)

    def upload(self, data, name='p.jpg', sheet=None, page_number=None, provider=None):
        """POST one file through the view and run the worker inline."""
        params = {'file': SimpleUploadedFile(name, data, content_type='application/octet-stream')}
        if sheet is not None:
            params['sheet'] = sheet.pk
        if page_number is not None:
            params['page_number'] = page_number
        with mock.patch('survey.ai.client.get_provider', return_value=provider or _blank_provider()), \
                _eager_tasks(), self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url('paper_upload'), params)
        self.assertEqual(response.status_code, 200, response.content)
        return PaperUpload.objects.get(pk=json.loads(response.content)['id'])

    def page_row(self, sheet=None, **fields):
        """A page row with an image, for tests about review rather than ingest."""
        batch = self.inbox
        upload = PaperUpload.objects.create(batch=batch, seq=batch.next_upload_seq, original_name='x.jpg', status='split')
        batch.next_upload_seq += 1
        page = PaperPage(batch=batch, upload=upload, seq=batch.next_page_seq, sheet=sheet, width=400, height=560, **fields)
        batch.next_page_seq += 1
        batch.save()
        page.image.save('p.jpg', ContentFile(_jpeg()), save=False)
        page.save()
        return page


# ── gate, pages ────────────────────────────────────────────────────────────

class PaperPagesGateTest(_PaperFixture):

    def test_editor_of_pro_workspace_opens_paper_responses(self):
        """
        GIVEN an owner of a Pro workspace
        WHEN they open Paper responses and press New response
        THEN the page offers New response and Upload a stack (with the camera), and New response
             makes an empty response and opens its card with a drop zone
        """
        page = self.client.get(self.url('paper_home'))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, self.url('paper_new'))
        self.assertContains(page, 'capture="environment"')
        response = self.client.post(self.url('paper_new'))
        sheet = PaperSheet.objects.get()
        self.assertIsNone(sheet.copy)
        self.assertRedirects(response, self.url('paper_response', sheet.pk), fetch_redirect_response=False)
        card = self.client.get(response['Location'])
        self.assertContains(card, 'data-paper-upload')
        self.assertContains(card, f'data-sheet="{sheet.pk}"')

    def test_viewer_cannot(self):
        """
        GIVEN a workspace viewer
        WHEN they request Paper responses
        THEN the response is 403
        """
        viewer = User.objects.create_user('paper_viewer', password='pass')
        Membership.objects.create(user=viewer, organization=self.org, role='viewer')
        self.login(viewer)
        self.assertEqual(self.client.get(self.url('paper_home')).status_code, 403)

    def test_free_workspace_sees_the_refusal(self):
        """
        GIVEN a workspace without Pro
        WHEN an owner requests Paper responses
        THEN the response is the feature refusal
        """
        self.sub.delete()
        response = self.client.get(self.url('paper_home'))
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, 'billing/feature_required.html')

    def test_another_surveys_response_is_404(self):
        """
        GIVEN a response of a different survey
        WHEN it is requested under this survey's URL
        THEN the response is 404
        """
        other = SurveyHeader.objects.create(name='other', organization=self.org, created_by=self.owner, redirect_url='#')
        sheet = sheets_mod.new_sheet(sheets_mod.inbox_for(other))
        self.assertEqual(self.client.get(self.url('paper_response', sheet.pk)).status_code, 404)

    def test_responses_offers_from_photos(self):
        """
        GIVEN a Pro workspace
        WHEN Responses renders
        THEN the Enter a response dropdown links to Paper responses
        """
        page = self.client.get(reverse('editor_survey_analytics', args=[self.survey.uuid]))
        self.assertContains(page, self.url('paper_home'))

    def test_home_shows_the_printed_forms_and_copies_back(self):
        """
        GIVEN 3 numbered copies printed and copy 2 photographed
        WHEN Paper responses renders
        THEN it names the form and says 1 of 3 numbered copies are back
        """
        result = self.print_copies(3)
        PaperSheet.objects.create(batch=self.inbox, seq=1, copy=2, printed_form=result.form)
        page = self.client.get(self.url('paper_home'))
        self.assertContains(page, f'MS-{result.form.code}')
        self.assertContains(page, '1 of 3 numbered copies back')


class UploadTest(_PaperFixture):

    def test_files_are_stored_and_queued_in_order(self):
        """
        GIVEN Paper responses
        WHEN three files are posted
        THEN three PaperUpload rows exist with seq 1..3, each with its file, and the ingest task is enqueued for each
        """
        from survey import tasks
        with mock.patch.object(tasks.ingest_paper_upload, 'delay') as delay, self.captureOnCommitCallbacks(execute=True):
            for name in ('a.jpg', 'b.jpg', 'c.jpg'):
                response = self.client.post(self.url('paper_upload'),
                                            {'file': SimpleUploadedFile(name, _jpeg(), content_type='image/jpeg')})
                self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(list(PaperUpload.objects.values_list('seq', flat=True)), [1, 2, 3])
        self.assertEqual(delay.call_count, 3)
        self.assertTrue(PaperUpload.objects.first().file)

    @override_settings(PAPER_UPLOAD_MAX_BYTES=1000)
    def test_file_too_large(self):
        """
        GIVEN a 40 KB file and a 1 KB limit
        WHEN it is posted
        THEN the response is 413 and nothing is stored
        """
        response = self.client.post(self.url('paper_upload'),
                                    {'file': SimpleUploadedFile('x.jpg', b'x' * 40000, content_type='image/jpeg')})
        self.assertEqual(response.status_code, 413)
        self.assertFalse(PaperUpload.objects.exists())

    def test_stored_response_refuses_more_photos(self):
        """
        GIVEN a stored response
        WHEN a photo is posted into it
        THEN the response is 409
        """
        sheet = sheets_mod.new_sheet(self.inbox)
        sheet.status = 'entered'
        sheet.save()
        response = self.client.post(self.url('paper_upload'), {
            'file': SimpleUploadedFile('x.jpg', _jpeg(), content_type='image/jpeg'), 'sheet': sheet.pk})
        self.assertEqual(response.status_code, 409)


# ── ingest and the code ────────────────────────────────────────────────────

class IngestTest(_PaperFixture):

    def _upload_row(self, data, name='scan.pdf'):
        batch = self.inbox
        upload = PaperUpload.objects.create(batch=batch, seq=batch.next_upload_seq, original_name=name, size=len(data))
        batch.next_upload_seq += 1
        batch.save()
        upload.file.save(name, ContentFile(data), save=True)
        return upload

    def test_sniff(self):
        """
        GIVEN the first bytes of a PDF, a JPEG, a PNG, a HEIC and a Word file
        WHEN they are sniffed
        THEN the kinds are pdf, image, image, image and None
        """
        self.assertEqual(sniff(b'%PDF-1.7'), 'pdf')
        self.assertEqual(sniff(b'\xff\xd8\xff\xe0'), 'image')
        self.assertEqual(sniff(b'\x89PNG\r\n\x1a\n'), 'image')
        self.assertEqual(sniff(b'\x00\x00\x00\x18ftypheic'), 'image')
        self.assertIsNone(sniff(b'PK\x03\x04'))

    def test_pdf_of_copies_is_split_and_every_page_knows_its_copy(self):
        """
        GIVEN 2 numbered copies printed as one PDF
        WHEN it is ingested
        THEN every page is a JPEG whose code (read locally, at ingest) names its copy and page,
             and the original is deleted
        """
        result = self.print_copies(2)
        upload = self._upload_row(result.pdf)
        created = ingest_upload(upload)
        upload.refresh_from_db()
        self.assertEqual(created, 2 * result.pages)
        self.assertTrue(upload.is_pdf)
        self.assertFalse(upload.file)
        codes = list(PaperPage.objects.order_by('seq').values_list('copy', 'page_number', 'code_source'))
        expected = [(c, p, 'qr') for c in (1, 2) for p in range(1, result.pages + 1)]
        self.assertEqual(codes, expected)

    def test_not_a_document(self):
        """
        GIVEN a .docx
        WHEN it is ingested
        THEN the upload is failed with "Not a photo or PDF", no page exists and the file is deleted
        """
        upload = self._upload_row(b'PK\x03\x04' + b'\x00' * 100, name='notes.docx')
        ingest_upload(upload)
        upload.refresh_from_db()
        self.assertEqual((upload.status, upload.error), ('failed', 'Not a photo or PDF'))
        self.assertFalse(PaperPage.objects.exists())
        self.assertFalse(upload.file)

    def test_big_photo_is_bounded_and_exif_upright(self):
        """
        GIVEN a 6000 x 4000 photo with an EXIF rotation of 90 degrees
        WHEN it is ingested
        THEN the stored page is at most 2200 px on its long side and upright (portrait)
        """
        img = Image.new('RGB', (6000, 4000), (200, 200, 200))
        exif = img.getexif()
        exif[0x0112] = 6
        buf = io.BytesIO()
        img.save(buf, format='JPEG', exif=exif.tobytes())
        ingest_upload(self._upload_row(buf.getvalue(), name='IMG_1.jpg'))
        page = PaperPage.objects.get()
        self.assertLessEqual(max(page.width, page.height), 2200)
        self.assertGreater(page.height, page.width)

    def test_heic_converts(self):
        """
        GIVEN an iPhone HEIC photo
        WHEN it is ingested
        THEN one page exists whose image is a JPEG
        """
        import pillow_heif
        heif = pillow_heif.from_pillow(Image.new('RGB', (300, 400), (10, 20, 30)))
        buf = io.BytesIO()
        heif.save(buf, format='HEIF')
        ingest_upload(self._upload_row(buf.getvalue(), name='IMG_2.heic'))
        with PaperPage.objects.get().image.open('rb') as fh:
            self.assertTrue(fh.read(3).startswith(b'\xff\xd8'))

    def test_pages_land_in_their_slots_before_any_read_and_reads_wait_for_the_uploads(self):
        """
        GIVEN two numbered pages uploaded one after the other
        WHEN the first is ingested while the second is still queued
        THEN its page is on its copy's response at once (status queued, no model call), and the
             reader re-arms itself instead of reading; once the second is ingested and the uploads
             are older than the settle window, the reader queues both pages in response and page order
        """
        from survey import tasks
        result = self.print_copies(1)
        p1, p2 = _pdf_page_jpegs(result.pdf, [0, 1])
        provider = _blank_provider()
        armed = []
        with mock.patch('survey.ai.client.get_provider', return_value=provider), \
                mock.patch.object(tasks.read_pending_pages, 'apply_async', side_effect=lambda args, countdown: armed.append(args)), \
                mock.patch.object(tasks.ingest_paper_upload, 'delay'), self.captureOnCommitCallbacks(execute=True):
            u2 = self.upload_only(p2, 'p2.jpg')
            u1 = self.upload_only(p1, 'p1.jpg')
            tasks.ingest_paper_upload(u1.pk)
            page1 = PaperPage.objects.get(upload=u1)
            self.assertEqual((page1.status, page1.copy, page1.page_number, page1.sheet.copy), ('queued', 1, 1, 1))
            self.assertEqual(provider.calls, [])
            self.assertEqual(armed, [(self.inbox.pk,)])
            tasks.read_pending_pages(self.inbox.pk)        # u2 still queued: re-armed, nothing read
            self.assertEqual(provider.calls, [])
            self.assertEqual(len(armed), 2)
            tasks.ingest_paper_upload(u2.pk)
            PaperUpload.objects.filter(batch=self.inbox).update(created_at=timezone.now() - timezone.timedelta(seconds=30))
            with mock.patch.object(tasks.recognise_paper_page, 'delay', side_effect=lambda pk: tasks.recognise_paper_page(pk)):
                tasks.read_pending_pages(self.inbox.pk)
        self.assertEqual(len(provider.calls), 2)
        self.assertEqual(sorted(PaperPage.objects.values_list('page_number', 'status')), [(1, 'recognised'), (2, 'recognised')])

    def upload_only(self, data, name):
        """POST one file through the view with the worker NOT run (ingest.delay is patched by the caller)."""
        response = self.client.post(self.url('paper_upload'), {
            'file': SimpleUploadedFile(name, data, content_type='application/octet-stream')})
        self.assertEqual(response.status_code, 200, response.content)
        return PaperUpload.objects.get(pk=json.loads(response.content)['id'])

    def test_ingest_is_idempotent(self):
        """
        GIVEN an upload already split
        WHEN the task runs again
        THEN no second set of pages is created
        """
        result = self.print_single()
        upload = self._upload_row(result.pdf)
        ingest_upload(upload)
        upload.refresh_from_db()
        ingest_upload(upload)
        self.assertEqual(PaperPage.objects.count(), result.pages)

    def test_old_and_new_payloads_parse(self):
        """
        GIVEN a pre-copy QR payload and a current one
        WHEN they are parsed
        THEN both give the form and page, the current one the copy (0 = none)
        """
        from survey.print import form_code
        self.assertEqual(form_code.parse('ms:form:4:2:10'), form_code.Code(2, None, 2, 10))
        self.assertEqual(form_code.parse('MSFORM:4:37:2:10'), form_code.Code(2, 37, 2, 10))
        self.assertEqual(form_code.parse('MSFORM:4:0:2:10'), form_code.Code(2, None, 2, 10))
        self.assertIsNone(form_code.parse('https://example.test/s/abc'))


# ── placement ──────────────────────────────────────────────────────────────

class PlacementTest(_PaperFixture):

    def test_stack_in_any_order_sorts_itself_by_copy(self):
        """
        GIVEN two numbered copies of a two-or-more page form
        WHEN their pages are uploaded as photos in a scrambled order (copy 2 p2, copy 1 p2, copy 2 p1, copy 1 p1)
        THEN two responses exist, Copy 1 and Copy 2, each holding its own pages 1 and 2
        """
        result = self.print_copies(2)
        n = result.pages
        photos = _pdf_page_jpegs(result.pdf, [n + 1, 1, n, 0])
        for i, jpeg in enumerate(photos):
            self.upload(jpeg, name=f'IMG_{i}.jpg')
        sheets = {s.copy: s for s in PaperSheet.objects.all()}
        self.assertEqual(sorted(sheets), [1, 2])
        for copy, sheet in sheets.items():
            numbers = sorted(sheet.pages.values_list('page_number', flat=True))
            self.assertEqual(numbers, [1, 2], copy)
            self.assertEqual(sheet.label, f'Copy {copy}')

    def test_new_response_takes_the_copy_of_its_first_page(self):
        """
        GIVEN an empty New response
        WHEN a photo of copy 1, page 1 is dropped into it
        THEN the response becomes Copy 1 and holds the page
        """
        result = self.print_copies(1)
        sheet = sheets_mod.new_sheet(self.inbox, user=self.owner)
        self.upload(_pdf_page_jpegs(result.pdf, [0])[0], sheet=sheet)
        sheet.refresh_from_db()
        self.assertEqual(sheet.copy, 1)
        self.assertEqual(list(sheet.pages.values_list('page_number', flat=True)), [1])

    def test_another_copys_page_goes_to_its_own_response_with_a_note(self):
        """
        GIVEN Copy 1 being filled in its card
        WHEN a photo of copy 2 is dropped into Copy 1's card
        THEN it goes to Copy 2 (made on first sight), and Copy 1's card names where it went
        """
        result = self.print_copies(2)
        n = result.pages
        a1, b1 = _pdf_page_jpegs(result.pdf, [0, n])
        sheet = sheets_mod.new_sheet(self.inbox, user=self.owner)
        self.upload(a1, sheet=sheet)
        self.upload(b1, name='wrong.jpg', sheet=sheet)
        copy2 = PaperSheet.objects.get(copy=2)
        self.assertEqual(copy2.pages.count(), 1)
        card = self.client.get(self.url('paper_response', sheet.pk))
        self.assertContains(card, 'Copy 2')
        self.assertContains(card, 'it went there')

    def test_same_page_twice_keeps_the_later_and_can_restore(self):
        """
        GIVEN Copy 1 page 1 photographed, then photographed again
        WHEN the second photo is placed
        THEN the first is `replaced`, the response counts one page 1, and restoring swaps them back
        """
        result = self.print_copies(1)
        jpeg = _pdf_page_jpegs(result.pdf, [0])[0]
        self.upload(jpeg, name='first.jpg')
        self.upload(jpeg, name='second.jpg')
        sheet = PaperSheet.objects.get(copy=1)
        first, second = sheet.pages.order_by('seq')
        self.assertEqual((first.status, second.status != 'replaced'), ('replaced', True))
        self.assertEqual(sheets_mod.active_pages(sheet).count(), 1)
        self.client.post(self.url('paper_page_restore', first.pk))
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(second.status, 'replaced')
        self.assertNotEqual(first.status, 'replaced')

    def test_notices_can_be_dismissed(self):
        """
        GIVEN Copy 3 with a replaced photo of page 1, and a photo of copy 7 dropped on Copy 3's card
        WHEN the operator presses × on both notices
        THEN the replaced photo is deleted, the copy-7 page stays on Copy 7 with its note cleared,
             and neither notice renders any more
        """
        result = self.print_copies(7)
        copy3 = sheets_mod.new_sheet(self.inbox, copy=3, printed_form=result.form)
        old = self.page_row(sheet=copy3, status='replaced', printed_form=result.form, copy=3, page_number=1, code_source='qr')
        self.page_row(sheet=copy3, status='recognised', printed_form=result.form, copy=3, page_number=1, code_source='qr')
        self.upload(_pdf_page_jpegs(result.pdf, [6 * result.form.pages])[0], sheet=copy3)
        went = PaperPage.objects.get(copy=7)
        page_url = self.url('paper_response', copy3.pk)
        html = self.client.get(page_url).content.decode()
        self.assertEqual(html.count('paper-note__x'), 2)
        for page in (old, went):
            response = self.client.post(self.url('paper_page_dismiss', page.pk), {'next': page_url})
            self.assertRedirects(response, page_url, fetch_redirect_response=False)
        self.assertFalse(PaperPage.objects.filter(pk=old.pk).exists())
        went.refresh_from_db()
        self.assertEqual((went.sheet.copy, went.error), (7, ''))
        self.assertNotIn('paper-note__x', self.client.get(page_url).content.decode())

    def test_unnumbered_loose_photo_is_set_aside(self):
        """
        GIVEN a form printed without copy numbers
        WHEN one of its pages is uploaded as a loose photo (not into a response)
        THEN the page is set aside with the reason, and Paper responses lists it with Attach
        """
        result = self.print_single()
        self.upload(_pdf_page_jpegs(result.pdf, [0])[0])
        page = PaperPage.objects.get()
        self.assertEqual((page.status, page.sheet_id), ('unrecognised', None))
        self.assertIn('no copy numbers', page.error)
        sheets_mod.new_sheet(self.inbox)   # something to attach it to
        home = self.client.get(self.url('paper_home'))
        self.assertContains(home, self.url('paper_page_assign', page.pk))

    def test_unnumbered_pdf_is_one_response(self):
        """
        GIVEN a form printed without copy numbers, scanned as one PDF per filled form
        WHEN two such PDFs are uploaded as a stack
        THEN each PDF is one response holding all its pages
        """
        result = self.print_single()
        self.upload(result.pdf, name='anna.pdf')
        self.upload(result.pdf, name='boris.pdf')
        sheets = list(PaperSheet.objects.order_by('seq'))
        self.assertEqual(len(sheets), 2)
        for sheet in sheets:
            self.assertIsNone(sheet.copy)
            self.assertEqual(sheets_mod.active_pages(sheet).count(), result.pages)
            self.assertEqual(sheet.label, f'Response {sheet.seq}')

    def test_unnumbered_photos_into_a_new_response(self):
        """
        GIVEN a form printed without copy numbers and a New response
        WHEN its pages are photographed into the response
        THEN the response holds them, by the page number in their code
        """
        result = self.print_single()
        sheet = sheets_mod.new_sheet(self.inbox)
        p2, p1 = _pdf_page_jpegs(result.pdf, [1, 0])
        self.upload(p2, sheet=sheet)
        self.upload(p1, sheet=sheet)
        self.assertEqual(sorted(sheet.pages.values_list('page_number', flat=True)), [1, 2])

    def test_photo_of_a_stored_copy_is_set_aside(self):
        """
        GIVEN Copy 1 already stored
        WHEN another photo of copy 1 arrives
        THEN it is set aside as "already stored"
        """
        result = self.print_copies(1)
        PaperSheet.objects.create(batch=self.inbox, seq=1, copy=1, printed_form=result.form, status='entered')
        self.upload(_pdf_page_jpegs(result.pdf, [0])[0])
        page = PaperPage.objects.get()
        self.assertEqual(page.status, 'unrecognised')
        self.assertIn('already stored', page.error)

    def test_page_of_another_surveys_form_is_set_aside(self):
        """
        GIVEN a photo of another survey's printed form
        WHEN it is uploaded here
        THEN it is set aside (no code that belongs to this survey)
        """
        from survey.print.pdf import build_form
        other = SurveyHeader.objects.create(name='other', organization=self.org, created_by=self.owner,
                                            redirect_url='#', status='published')
        s = SurveySection.objects.create(survey_header=other, name='a', title='A', code='A', is_head=True, layout='form')
        Question.objects.create(survey_section=s, code='Q', name='Q?', input_type='text', order_number=1)
        with override_settings(MAPBOX_ACCESS_TOKEN=''):
            foreign = build_form(other, 'en', 'a4', base_url='https://example.test')
        self.upload(_pdf_page_jpegs(foreign.pdf, [0])[0])
        self.assertEqual(PaperPage.objects.get().status, 'unrecognised')
        self.assertFalse(PaperSheet.objects.exists())

    def test_set_aside_photo_is_attached_by_hand(self):
        """
        GIVEN a set-aside photo and an open response missing page 2
        WHEN the operator attaches it as page 2
        THEN the page joins the response as page 2 (code_source manual) and is read
        """
        result = self.print_copies(1)
        sheet = PaperSheet.objects.create(batch=self.inbox, seq=1, copy=1, printed_form=result.form)
        page = self.page_row(status='unrecognised')
        provider = _FakeProvider([{'fields': [{'code': 'MOOD', 'value': ['1'], 'confidence': 0.9, 'unreadable': False}]}])
        with mock.patch('survey.ai.client.get_provider', return_value=provider), _eager_tasks(), \
                self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url('paper_page_assign', page.pk), {'sheet': sheet.pk, 'page_number': 2})
        page.refresh_from_db()
        self.assertEqual((page.sheet_id, page.page_number, page.code_source, page.status),
                         (sheet.pk, 2, 'manual', 'recognised'))

    def test_first_page_link_qr_names_page_one_of_the_response(self):
        """
        GIVEN a form printed without copy numbers and a New response
        WHEN a photo of page 1 with its footer cut off (only the "answer online" QR in frame) is dropped in
        THEN the page joins the response as page 1, read from the link QR, no model asked for a code
        """
        result = self.print_single()
        sheet = sheets_mod.new_sheet(self.inbox)
        with Image.open(io.BytesIO(_pdf_page_jpegs(result.pdf, [0])[0])) as img:
            buf = io.BytesIO()
            img.crop((0, 0, img.width, img.height // 3)).save(buf, format='JPEG', quality=90)
        self.upload(buf.getvalue(), sheet=sheet)
        page = PaperPage.objects.get()
        self.assertEqual((page.sheet_id, page.page_number, page.code_source), (sheet.pk, 1, 'qr'))

    def test_link_qr_of_another_survey_is_not_page_one(self):
        """
        GIVEN the page-1 link of another survey, and a mangled one of this survey
        WHEN they are checked
        THEN neither counts as this survey's first page; the real one does
        """
        from survey.paper import codes
        good = f'https://example.test/surveys/{self.survey.uuid}/?utm_source=paper&utm_medium=print_form'
        self.assertTrue(codes.is_first_page_link(good, self.survey.uuid))
        self.assertFalse(codes.is_first_page_link(good.replace(str(self.survey.uuid), str(uuid.uuid4())), self.survey.uuid))
        self.assertFalse(codes.is_first_page_link(good.replace('print_form', 'qr'), self.survey.uuid))

    def test_codeless_photo_dropped_here_offers_which_page(self):
        """
        GIVEN a response missing page 1 and a photo dropped into it whose code cannot be read
        WHEN the response page renders and the operator says "It is page 1"
        THEN the warning carries the page picker (page 1 preselected), and the photo joins the response as page 1
        """
        result = self.print_copies(1)
        sheet = PaperSheet.objects.create(batch=self.inbox, seq=1, copy=1, printed_form=result.form)
        self.page_row(sheet=sheet, status='recognised', printed_form=result.form, copy=1, page_number=2, code_source='qr')
        self.upload(_jpeg(), name='blurry.jpg', sheet=sheet)
        loose = PaperPage.objects.get(sheet__isnull=True)
        html = self.client.get(self.url('paper_response', sheet.pk)).content.decode()
        self.assertIn('paper-attach-here', html)
        self.assertIn('<option value="1" selected>', html)
        with mock.patch('survey.ai.client.get_provider', return_value=_blank_provider()), _eager_tasks(), \
                self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url('paper_page_assign', loose.pk), {
                'sheet': sheet.pk, 'page_number': 1, 'next': self.url('paper_response', sheet.pk)})
        self.assertRedirects(response, self.url('paper_response', sheet.pk), fetch_redirect_response=False)
        loose.refresh_from_db()
        self.assertEqual((loose.sheet_id, loose.page_number), (sheet.pk, 1))


# ── extraction ─────────────────────────────────────────────────────────────

class ExtractionTest(_PaperFixture):

    def setUp(self):
        super().setUp()
        self.form = PrintedForm.objects.create(survey=self.survey, version_number=1, language='en',
                                               structure_hash='h', pages=2)
        self.sheet = PaperSheet.objects.create(batch=self.inbox, seq=1, copy=1, printed_form=self.form)

    def _page(self, number=1, layout_items=None):
        if layout_items is not None:
            self.form.layout = {str(number): {'items': layout_items}}
            self.form.save()
        return self.page_row(sheet=self.sheet, status='queued', printed_form=self.form, copy=1,
                             page_number=number, pages_total=2, code_source='qr')

    def test_items_bounded_by_the_page(self):
        """
        GIVEN page 1 holds ALB and WHY
        WHEN page 1 is extracted
        THEN the provider sees one image and exactly ALB and WHY, and the values come back typed
        """
        page = self._page(1, ['section:S1', 'question:ALB', 'question:WHY'])
        provider = _FakeProvider([{'fields': [
            {'code': 'ALB', 'value': '1', 'confidence': 0.95, 'unreadable': False},
            {'code': 'WHY', 'value': 'Too dark at night', 'confidence': 0.8, 'unreadable': False},
            {'code': 'WHERE', 'value': 'x', 'confidence': 0.9, 'unreadable': False},
        ]}])
        extraction, _usage, items = extract.extract_page(page, provider)
        self.assertEqual([i['code'] for i in items], ['ALB', 'WHY'])
        request = provider.requests[0]
        self.assertEqual([m for m, _b in request['images']], ['image/jpeg'])
        self.assertIn('1 = Yes', request['user'])
        self.assertNotIn('WHERE', request['user'])
        self.assertEqual((extraction['ALB']['value'], extraction['WHY']['value']), ('1', 'Too dark at night'))
        self.assertNotIn('WHERE', extraction)

    def test_geo_is_never_asked_and_whole_form_fallback(self):
        """
        GIVEN a PrintedForm whose layout has no items map
        WHEN a page of it is extracted
        THEN the whole structure is sent minus the geo question, with the "only what the page shows" instruction
        """
        page = self._page(2)
        provider = _FakeProvider([{'fields': []}])
        _extraction, _usage, items = extract.extract_page(page, provider)
        self.assertEqual([i['code'] for i in items], ['ALB', 'WHY', 'MOOD'])
        self.assertIn('ONE of its pages', provider.requests[0]['user'])

    def test_values_are_checked_against_the_question(self):
        """
        GIVEN the model answers an option code the question lacks, a write-in and a list for a multichoice
        WHEN the fields are coerced
        THEN the bad code is null and doubtful, the write-in lands in the companion field, the list is codes
        """
        items = [extract.describe_question(self.alb, 'en'), extract.describe_question(self.mood, 'en')]
        out = extract.coerce_fields([
            {'code': 'ALB', 'value': '7', 'confidence': 0.99, 'unreadable': False},
            {'code': 'MOOD', 'value': ['2', '1'], 'confidence': 0.9, 'unreadable': False},
            {'code': 'MOOD__other', 'value': 'tired', 'confidence': 0.7, 'unreadable': False},
            {'code': 'NOPE', 'value': 'x', 'confidence': 1, 'unreadable': False},
        ], items)
        self.assertIsNone(out['ALB']['value'])
        self.assertTrue(extract.is_doubtful(out['ALB']))
        self.assertEqual(out['MOOD']['value'], ['2', '1'])
        self.assertEqual(out['MOOD-other']['value'], 'tired')
        self.assertNotIn('NOPE', out)

    def test_boxes_are_kept_when_sane(self):
        """
        GIVEN the model's boxes: a good one, one out of range, one inside out and one of three numbers
        WHEN the fields are coerced
        THEN only the good box is kept, as [ymin, xmin, ymax, xmax] in 0..1000, and page_boxes lists it
        """
        items = [extract.describe_question(q, 'en') for q in (self.alb, self.why, self.mood)]
        out = extract.coerce_fields([
            {'code': 'ALB', 'value': '1', 'confidence': 0.9, 'unreadable': False, 'box': [100, 50, 180.4, 900]},
            {'code': 'WHY', 'value': 'x', 'confidence': 0.9, 'unreadable': False, 'box': [100, 50, 1200, 900]},
            {'code': 'MOOD', 'value': ['1'], 'confidence': 0.9, 'unreadable': False, 'box': [300, 50, 200, 900]},
            {'code': 'MOOD__other', 'value': 'x', 'confidence': 0.9, 'unreadable': False, 'box': [1, 2, 3]},
        ], items)
        self.assertEqual(out['ALB']['box'], [100, 50, 180, 900])
        self.assertNotIn('box', out['WHY'])
        self.assertNotIn('box', out['MOOD'])
        page = self._page(1)
        page.extraction = out
        self.assertEqual(extract.page_boxes(page), {'ALB': [100, 50, 180, 900]})

    def test_dates_become_what_the_datetime_input_holds(self):
        """
        GIVEN a datetime question and the model's answers in ISO, day-first, with a time, and nonsense
        WHEN the fields are coerced
        THEN each becomes 'YYYY-MM-DDTHH:MM' (the datetime-local value), a date without a time gets 00:00
             and is doubtful, and an unreadable date is null and doubtful
        """
        item = {'code': 'WHEN', 'type': 'datetime', 'name': 'When?'}

        def one(value, confidence=0.95):
            return extract.coerce_fields([{'code': 'WHEN', 'value': value, 'confidence': confidence,
                                           'unreadable': False}], [item])['WHEN']
        self.assertEqual(one('2026-10-30T14:05')['value'], '2026-10-30T14:05')
        self.assertFalse(extract.is_doubtful(one('2026-10-30T14:05')))
        self.assertEqual(one('30/10/2026 9:30')['value'], '2026-10-30T09:30')
        no_time = one('30.10.2026')
        self.assertEqual(no_time['value'], '2026-10-30T00:00')
        self.assertTrue(extract.is_doubtful(no_time))
        bad = one('last summer')
        self.assertIsNone(bad['value'])
        self.assertTrue(extract.is_doubtful(bad))

    def test_doubtful_count_and_merge(self):
        """
        GIVEN two read pages, the first with WHY at confidence 0.4 and the second repeating ALB
        WHEN the response is refreshed
        THEN the earlier page's ALB wins and doubtful_count is 1
        """
        self._page(1).__class__.objects.filter(page_number=1).update(
            status='recognised', extraction={'ALB': _field('1'), 'WHY': _field('dark', 0.4)})
        p2 = self._page(2)
        PaperPage.objects.filter(pk=p2.pk).update(status='recognised', extraction={'ALB': _field('0')})
        sheets_mod.refresh_sheet(self.sheet)
        self.sheet.refresh_from_db()
        self.assertEqual(self.sheet.extraction['ALB']['value'], '1')
        self.assertEqual(self.sheet.doubtful_count, 1)

    def test_provider_down_marks_the_page_failed_and_costs_every_call(self):
        """
        GIVEN a provider that answers a transient error every time
        WHEN the page task runs out of retries
        THEN the page is failed, no Answer exists, and every call is accounted
        """
        from survey import tasks
        page = self._page(1, ['question:ALB'])
        provider = _FakeProvider([], error=ProviderError('API error 503: busy', transient=True))
        with mock.patch('survey.ai.client.get_provider', return_value=provider):
            tasks.recognise_paper_page.apply(args=(page.pk,), retries=0, throw=False)
        self.assertEqual(len(provider.calls), tasks.PAPER_PAGE_RETRIES + 1)
        page.refresh_from_db()
        self.assertEqual(page.status, 'failed')
        self.assertEqual(Answer.objects.count(), 0)
        events = AIGenerationEvent.objects.filter(kind='paper_page')
        self.assertEqual(events.count(), tasks.PAPER_PAGE_RETRIES + 1)
        self.assertTrue(all(e.outcome == 'provider_error' for e in events))

    def test_event_and_posthog_generation_per_call(self):
        """
        GIVEN a page placed on its response
        WHEN it is read
        THEN one AIGenerationEvent(paper_page, success) exists and one $ai_generation was captured with
             span paper_page, trace paper-response-<id>, the token counts and no content
        """
        import posthog
        from survey import tasks
        page = self._page(1, ['question:ALB'])
        provider = _FakeProvider([{'fields': [{'code': 'ALB', 'value': '1', 'confidence': 0.9, 'unreadable': False}]}])
        with mock.patch('survey.ai.client.get_provider', return_value=provider), \
                mock.patch.object(posthog, 'disabled', False), mock.patch('posthog.capture') as capture:
            tasks.recognise_paper_page(page.pk)
        event = AIGenerationEvent.objects.get(kind='paper_page')
        self.assertEqual((event.outcome, event.organization, event.input_tokens), ('success', self.org, 100))
        generations = [c for c in capture.call_args_list if c.args[0] == '$ai_generation']
        self.assertEqual(len(generations), 1)
        props = generations[0].kwargs['properties']
        self.assertEqual((props['$ai_span_name'], props['$ai_trace_id']), ('paper_page', f'paper-response-{self.sheet.pk}'))
        self.assertEqual(props['$ai_input_tokens'], 100)
        self.assertFalse(any('Albino' in str(v) for v in props.values()))
        recognised = [c for c in capture.call_args_list if c.args[0] == 'paper_page_recognised']
        self.assertEqual(recognised[0].kwargs['properties']['outcome'], 'recognised')

    def test_no_model_reads_a_code(self):
        """
        GIVEN a photo whose code cannot be read, not dropped into a response
        WHEN it is recognised
        THEN it is set aside and the provider is never called
        """
        from survey import tasks
        page = self.page_row(status='queued')
        provider = _FakeProvider([])
        with mock.patch('survey.ai.client.get_provider', return_value=provider):
            tasks.recognise_paper_page(page.pk)
        page.refresh_from_db()
        self.assertEqual(page.status, 'unrecognised')
        self.assertEqual(provider.calls, [])

    def test_quota_is_asked_before_the_call(self):
        """
        GIVEN a workspace whose page allowance is spent (check_quota raises)
        WHEN a placed page is read
        THEN the page is failed, the provider is never called and no AIGenerationEvent exists
        """
        from survey import tasks
        from survey.ai.quota import QuotaExceeded
        page = self._page(1, ['question:ALB'])
        provider = _FakeProvider([])
        with mock.patch('survey.ai.client.get_provider', return_value=provider), \
                mock.patch('survey.ai.quota.check_quota', side_effect=QuotaExceeded) as quota:
            tasks.recognise_paper_page(page.pk)
        quota.assert_called_once_with(self.org, 'paper_page')
        page.refresh_from_db()
        self.assertEqual(page.status, 'failed')
        self.assertEqual(provider.calls, [])
        self.assertFalse(AIGenerationEvent.objects.filter(kind='paper_page').exists())


# ── marks on the printed map → coordinates (item 4) ────────────────────────

class MarksTest(_PaperFixture):
    """A map page of the printed form, photographed straight and at an angle."""

    def setUp(self):
        super().setUp()
        self.note = Question.objects.create(
            survey_section=self.s2, code='NOTE', name='Why here?', input_type='text', order_number=1,
            parent_question_id=self.where)
        self.result = self.print_single()
        self.form = self.result.form
        self.map_page = next(int(n) for n, rec in self.form.layout.items() if 'map' in rec)
        self.rec = self.form.layout[str(self.map_page)]['map']
        self.render = _pdf_page_jpegs(self.result.pdf, [self.map_page - 1])[0]

    def _image(self, jpeg):
        return Image.open(io.BytesIO(jpeg)).convert('RGB')

    def _mm_to_px(self, x_mm, y_mm, img):
        return x_mm / marks.PAGE_MM['a4'][0] * img.width, y_mm / marks.PAGE_MM['a4'][1] * img.height

    def test_squares_register_a_straight_render(self):
        """
        GIVEN a 200-dpi render of the map page
        WHEN the alignment squares are found and the homography built
        THEN all four are found and the frame's top-left corner maps to its printed millimetres within 1 mm
        """
        img = self._image(self.render)
        squares = marks.find_alignment_squares(img)
        self.assertIsNotNone(squares)
        self.assertEqual(len(squares), 4)
        h = marks.homography(squares, marks.page_square_centres('a4'))
        px = self._mm_to_px(self.rec['x_mm'], self.rec['y_mm'], img)
        x_mm, y_mm = marks.apply(h, *px)
        self.assertAlmostEqual(x_mm, self.rec['x_mm'], delta=1.0)
        self.assertAlmostEqual(y_mm, self.rec['y_mm'], delta=1.0)

    def test_squares_register_a_phone_shot_at_an_angle(self):
        """
        GIVEN the same page warped as a phone photo taken at an angle, on a dark table
        WHEN the squares are found and the homography built
        THEN a point known on the page maps back to its millimetres within 2 mm
        """
        img = self._image(self.render)
        w, hgt = img.size
        src = [(0, 0), (w, 0), (0, hgt), (w, hgt)]
        dst = [(0.12 * w, 0.08 * hgt), (0.86 * w, 0.14 * hgt), (0.05 * w, 0.93 * hgt), (0.95 * w, 0.88 * hgt)]
        back = marks.homography(dst, src)        # output pixel → source pixel, what PIL wants
        coeffs = [back[0][0], back[0][1], back[0][2], back[1][0], back[1][1], back[1][2], back[2][0], back[2][1]]
        warped = img.transform((w, hgt), Image.PERSPECTIVE, coeffs, Image.BILINEAR, fillcolor=(70, 60, 50))
        squares = marks.find_alignment_squares(warped)
        self.assertIsNotNone(squares)
        h = marks.homography(squares, marks.page_square_centres('a4'))
        forward = marks.homography(src, dst)
        centre_mm = (self.rec['x_mm'] + self.rec['w_mm'] / 2, self.rec['y_mm'] + self.rec['h_mm'] / 2)
        warped_px = marks.apply(forward, *self._mm_to_px(*centre_mm, img))
        x_mm, y_mm = marks.apply(h, *warped_px)
        self.assertAlmostEqual(x_mm, centre_mm[0], delta=2.0)
        self.assertAlmostEqual(y_mm, centre_mm[1], delta=2.0)

    def test_frame_fiducials_register_a_photo_cropped_to_the_map(self):
        """
        GIVEN the map page photographed at an angle and cropped to the map (no page corner in it)
        WHEN the frame's own corner squares are searched around the model's frame box
        THEN all four are found, the frame registers through them ("fiducials") and the frame's centre
             maps to its millimetres within 1.5 mm
        """
        img = self._image(self.render)
        w, hgt = img.size
        src = [(0, 0), (w, 0), (0, hgt), (w, hgt)]
        dst = [(0.10 * w, 0.06 * hgt), (0.90 * w, 0.12 * hgt), (0.04 * w, 0.94 * hgt), (0.96 * w, 0.90 * hgt)]
        back = marks.homography(dst, src)
        coeffs = [back[0][0], back[0][1], back[0][2], back[1][0], back[1][1], back[1][2], back[2][0], back[2][1]]
        warped = img.transform((w, hgt), Image.PERSPECTIVE, coeffs, Image.BILINEAR, fillcolor=(70, 60, 50))
        forward = marks.homography(src, dst)
        rec = self.rec
        corners_mm = [(rec['x_mm'], rec['y_mm']), (rec['x_mm'] + rec['w_mm'], rec['y_mm']),
                      (rec['x_mm'], rec['y_mm'] + rec['h_mm']), (rec['x_mm'] + rec['w_mm'], rec['y_mm'] + rec['h_mm'])]
        warped_corners = [marks.apply(forward, *self._mm_to_px(x, y, img)) for x, y in corners_mm]
        xs, ys = [c[0] for c in warped_corners], [c[1] for c in warped_corners]
        # Crop to the map plus a margin: no page corner square survives.
        crop = (int(min(xs) - 60), int(min(ys) - 60), int(max(xs) + 60), int(max(ys) + 60))
        cropped = warped.crop(crop)
        self.assertIsNone(marks.find_alignment_squares(cropped))
        cw, ch = cropped.size
        # The model's box: the axis-aligned bounds of the frame, a touch loose.
        frame_box = [int((min(ys) - crop[1]) / ch * 1000) - 8, int((min(xs) - crop[0]) / cw * 1000) - 8,
                     int((max(ys) - crop[1]) / ch * 1000) + 8, int((max(xs) - crop[0]) / cw * 1000) + 8]
        self.assertTrue(rec.get('fiducials'))
        h, source = marks.photo_to_page(cropped, 'a4', frame_box=frame_box, map_rec=rec)
        self.assertEqual(source, 'edges+fiducials')
        centre_mm = (rec['x_mm'] + rec['w_mm'] / 2, rec['y_mm'] + rec['h_mm'] / 2)
        wc = marks.apply(forward, *self._mm_to_px(*centre_mm, img))
        x_mm, y_mm = marks.apply(h, wc[0] - crop[0], wc[1] - crop[1])
        self.assertAlmostEqual(x_mm, centre_mm[0], delta=1.5)
        self.assertAlmostEqual(y_mm, centre_mm[1], delta=1.5)

    def test_bent_page_is_corrected_by_the_mid_side_fiducials(self):
        """
        GIVEN the map page photographed at an angle AND bent along its long axis (a page on a lap:
              every row shifts sideways by up to 12 px, most in the middle), with the dark table around it
        WHEN the photo is registered with the corner and mid-side fiducials plus the page squares
        THEN six fiducials are found, the plane alone misses the middle of the frame by millimetres, and the
             bend correction brings every probe inside the frame to within 1 mm
        """
        import math
        img = self._image(self.render)
        w, hgt = img.size
        src = [(0, 0), (w, 0), (0, hgt), (w, hgt)]
        dst = [(0.10 * w, 0.06 * hgt), (0.90 * w, 0.12 * hgt), (0.04 * w, 0.94 * hgt), (0.96 * w, 0.90 * hgt)]
        back = marks.homography(dst, src)
        coeffs = [back[0][0], back[0][1], back[0][2], back[1][0], back[1][1], back[1][2], back[2][0], back[2][1]]
        warped = img.transform((w, hgt), Image.PERSPECTIVE, coeffs, Image.BILINEAR, fillcolor=(70, 60, 50))
        forward = marks.homography(src, dst)
        amp = 12.0

        def bend(x, y):   # the page's bend after the perspective: rows slide sideways
            return x + amp * math.sin(math.pi * y / hgt), y
        # Render the bend with a mesh of row bands, each an affine strip.
        mesh, band = [], 40
        for top in range(0, hgt, band):
            bottom = min(hgt, top + band)
            s0, s1 = amp * math.sin(math.pi * top / hgt), amp * math.sin(math.pi * bottom / hgt)
            mesh.append(((0, top, w, bottom), (-s0, top, -s1, bottom, w - s1, bottom, w - s0, top)))
        bent = warped.transform((w, hgt), Image.MESH, mesh, Image.BILINEAR, fillcolor=(70, 60, 50))
        rec = self.rec
        self.assertTrue(rec.get('fiducial_mids'))
        corners_mm = [(rec['x_mm'], rec['y_mm']), (rec['x_mm'] + rec['w_mm'], rec['y_mm']),
                      (rec['x_mm'], rec['y_mm'] + rec['h_mm']), (rec['x_mm'] + rec['w_mm'], rec['y_mm'] + rec['h_mm'])]
        pts = [bend(*marks.apply(forward, *self._mm_to_px(x, y, img))) for x, y in corners_mm]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        frame_box = [int(min(ys) / hgt * 1000) - 8, int(min(xs) / w * 1000) - 8, int(max(ys) / hgt * 1000) + 8, int(max(xs) / w * 1000) + 8]
        fiducials = marks.find_frame_fiducials(bent, frame_box, rec)
        self.assertEqual(sum(1 for f in fiducials if f), 6)
        reg, source = marks.photo_to_page(bent, 'a4', frame_box=frame_box, map_rec=rec)
        self.assertEqual(source, 'edges+fiducials+squares')
        self.assertIsNotNone(reg['tps'])
        probes = [(0.25, 0.5), (0.5, 0.5), (0.75, 0.5), (0.5, 0.2), (0.5, 0.8), (0.68, 0.93)]
        plane_errors, bent_errors = [], []
        for fx, fy in probes:
            tx, ty = rec['x_mm'] + fx * rec['w_mm'], rec['y_mm'] + fy * rec['h_mm']
            p = bend(*marks.apply(forward, *self._mm_to_px(tx, ty, img)))
            for store, mapping in ((plane_errors, reg['h']), (bent_errors, reg)):
                mx, my = marks.apply(mapping, *p)
                store.append(((mx - tx) ** 2 + (my - ty) ** 2) ** 0.5)
        self.assertLess(max(bent_errors), 1.0)
        self.assertLess(max(bent_errors), max(plane_errors))

    def _textured_map(self, size=(900, 550), seed=7):
        """A stand-in for the printed basemap: grey strokes and boxes everywhere, so every
        patch of it has something to match (the test suite fetches no real tiles)."""
        import random

        from PIL import ImageDraw
        rng = random.Random(seed)
        ref = Image.new('L', size, 235)
        draw = ImageDraw.Draw(ref)
        for _ in range(300):
            x, y = rng.randrange(size[0]), rng.randrange(size[1])
            draw.line([x, y, x + rng.randint(-60, 60), y + rng.randint(-60, 60)], fill=rng.randint(165, 215), width=rng.randint(2, 3))
        for _ in range(120):
            x, y = rng.randrange(size[0]), rng.randrange(size[1])
            draw.rectangle([x, y, x + rng.randint(8, 40), y + rng.randint(8, 40)], outline=rng.randint(170, 210), width=2)
        return ref

    def test_bow_inside_the_frame_is_corrected_by_the_printed_map(self):
        """
        GIVEN the map page with a textured map in its frame, photographed at an angle, with a bow INSIDE
              the frame only — the middle of the map slides 4 mm sideways, its border and the fiducials not at all
              (a lap shot: the border registered to 0.3 mm and a dot near the bottom edge was still 5.5 mm off)
        WHEN the photo is registered without and with the printed map as the reference
        THEN the border alone misses the middle of the frame by millimetres; with the reference the interior
             landmarks join the fit (`interior` in the source) and every probe lands within 1 mm
        """
        import math

        from survey.paper import texture
        img = self._image(self.render)
        w, hgt = img.size
        rec = self.rec
        x0, y0 = self._mm_to_px(rec['x_mm'], rec['y_mm'], img)
        x1, y1 = self._mm_to_px(rec['x_mm'] + rec['w_mm'], rec['y_mm'] + rec['h_mm'], img)
        ref = self._textured_map()
        inset = 3   # keep the printed border line
        img.paste(ref.resize((int(x1 - x0) - 2 * inset, int(y1 - y0) - 2 * inset)).convert('RGB'),
                  (int(x0) + inset, int(y0) + inset))
        src = [(0, 0), (w, 0), (0, hgt), (w, hgt)]
        dst = [(0.10 * w, 0.06 * hgt), (0.90 * w, 0.12 * hgt), (0.04 * w, 0.94 * hgt), (0.96 * w, 0.90 * hgt)]
        back = marks.homography(dst, src)
        coeffs = [back[0][0], back[0][1], back[0][2], back[1][0], back[1][1], back[1][2], back[2][0], back[2][1]]
        warped = img.transform((w, hgt), Image.PERSPECTIVE, coeffs, Image.BILINEAR, fillcolor=(70, 60, 50))
        forward = marks.homography(src, dst)
        amp = 4.0 * w / marks.PAGE_MM['a4'][0]   # 4 mm, in page pixels

        def slide(X, Y):   # sideways slide of the warped image at (X, Y): a bump inside the frame, zero at its border
            px, py = marks.apply(back, X, Y)
            fx, fy = (px - x0) / (x1 - x0), (py - y0) / (y1 - y0)
            if not (0 < fx < 1 and 0 < fy < 1):
                return 0.0
            return amp * math.sin(math.pi * fx) * math.sin(math.pi * fy)
        mesh, cell = [], 24
        for top in range(0, hgt, cell):
            for left in range(0, w, cell):
                bottom, right = min(hgt, top + cell), min(w, left + cell)
                quad = []
                for X, Y in ((left, top), (left, bottom), (right, bottom), (right, top)):
                    quad += [X - slide(X, Y), Y]
                mesh.append(((left, top, right, bottom), tuple(quad)))
        bent = warped.transform((w, hgt), Image.MESH, mesh, Image.BILINEAR, fillcolor=(70, 60, 50))

        def photo_px(x_mm, y_mm):   # where a page point ended up: perspective, then the slide (fixed point)
            sx, sy = marks.apply(forward, *self._mm_to_px(x_mm, y_mm, img))
            X = sx
            for _ in range(8):
                X = sx + slide(X, sy)
            return X, sy
        corners_mm = [(rec['x_mm'], rec['y_mm']), (rec['x_mm'] + rec['w_mm'], rec['y_mm']),
                      (rec['x_mm'], rec['y_mm'] + rec['h_mm']), (rec['x_mm'] + rec['w_mm'], rec['y_mm'] + rec['h_mm'])]
        pts = [photo_px(x, y) for x, y in corners_mm]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        frame_box = [int(min(ys) / hgt * 1000) - 8, int(min(xs) / w * 1000) - 8, int(max(ys) / hgt * 1000) + 8, int(max(xs) / w * 1000) + 8]
        probes = [(0.5, 0.5), (0.3, 0.4), (0.7, 0.6), (0.5, 0.85), (0.85, 0.5), (0.2, 0.2)]

        def errors(reg):
            out = []
            for fx, fy in probes:
                tx, ty = rec['x_mm'] + fx * rec['w_mm'], rec['y_mm'] + fy * rec['h_mm']
                mx, my = marks.apply(reg, *photo_px(tx, ty))
                out.append(((mx - tx) ** 2 + (my - ty) ** 2) ** 0.5)
            return out
        border_only, source = marks.photo_to_page(bent, 'a4', frame_box=frame_box, map_rec=rec)
        self.assertNotIn('interior', source)
        self.assertGreater(errors(border_only)[0], 2.0)
        with_map, source = marks.photo_to_page(bent, 'a4', frame_box=frame_box, map_rec=rec, reference=ref)
        self.assertIn('interior', source)
        self.assertEqual(texture.REF_WIDTH, ref.width)
        self.assertLess(max(errors(with_map)), 1.0)

    def test_point_moves_from_the_label_to_the_dot(self):
        """
        GIVEN the map page with a textured map, a 2-mm BLACK ink dot at (0.4, 0.6) of the frame and "A1" written
              4 mm to its right, and the model reporting A1 on the letters and A2 where there is no ink at all
        WHEN the page is extracted with the printed map as the reference
        THEN A1 lands on the dot within 0.5 mm (the black pen's ink, read from reference − photo), A2 stays
             where the model put it, the field counts one mark from the ink, and the raw marks keep what the
             model said
        """
        from PIL import ImageDraw, ImageFont
        img = self._image(self.render)
        w, hgt = img.size
        rec = self.rec
        x0, y0 = self._mm_to_px(rec['x_mm'], rec['y_mm'], img)
        x1, y1 = self._mm_to_px(rec['x_mm'] + rec['w_mm'], rec['y_mm'] + rec['h_mm'], img)
        ref = self._textured_map()
        img.paste(ref.resize((int(x1 - x0) - 6, int(y1 - y0) - 6)).convert('RGB'), (int(x0) + 3, int(y0) + 3))
        px_per_mm = w / marks.PAGE_MM['a4'][0]
        dot_mm = (rec['x_mm'] + 0.4 * rec['w_mm'], rec['y_mm'] + 0.6 * rec['h_mm'])
        dx, dy = self._mm_to_px(*dot_mm, img)
        draw = ImageDraw.Draw(img)
        draw.ellipse([dx - px_per_mm, dy - px_per_mm, dx + px_per_mm, dy + px_per_mm], fill=(25, 25, 25))
        draw.text((dx + 4 * px_per_mm, dy - 3 * px_per_mm), 'A1', fill=(25, 25, 25), font=ImageFont.load_default(size=int(6 * px_per_mm)))
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=90)
        sheet = sheets_mod.new_sheet(self.inbox, printed_form=self.form)
        page = self.page_row(sheet=sheet, status='queued', printed_form=self.form, copy=None,
                             page_number=self.map_page, pages_total=self.form.pages, code_source='qr')
        page.image.save('dot.jpg', ContentFile(buf.getvalue()), save=True)
        label_frac = (0.4 + 6.0 / rec['w_mm'], 0.6)   # the middle of the letters
        provider = _FakeProvider([{'fields': [], 'marks': [
            {'label': 'A1', 'question': 'WHERE', 'points': [self._mark_at(*label_frac)], 'confidence': 0.9, 'answers': []},
            {'label': 'A2', 'question': 'WHERE', 'points': [self._mark_at(0.7, 0.3)], 'confidence': 0.9, 'answers': []},
        ]}])
        with mock.patch('survey.paper.texture.reference_image', return_value=ref):
            extraction, _usage, _items = extract.extract_page(page, provider)
        field = extraction['WHERE']
        self.assertEqual(field['from_ink'], 1)
        self.assertEqual(field['feature_labels'], ['A1', 'A2'])
        west, south, east, north = rec['bbox']
        tol = (0.5 / rec['w_mm'] * (east - west), 0.5 / rec['h_mm'] * (north - south))
        a1, a2 = (f['geometry']['coordinates'] for f in field['value'])
        want = marks.mm_to_lnglat(dot_mm[0], dot_mm[1], rec)
        self.assertAlmostEqual(a1[0], want[0], delta=tol[0])
        self.assertAlmostEqual(a1[1], want[1], delta=tol[1])
        want = marks.mm_to_lnglat(rec['x_mm'] + 0.7 * rec['w_mm'], rec['y_mm'] + 0.3 * rec['h_mm'], rec)
        self.assertAlmostEqual(a2[0], want[0], delta=tol[0])
        self.assertAlmostEqual(a2[1], want[1], delta=tol[1])
        self.assertEqual(field['marks'][0]['points'], [self._mark_at(*label_frac)])

    def test_marks_come_from_the_ink_and_the_model_names_them(self):
        """
        GIVEN a frame with four map questions (A dot, B line, C area, D spray) and, in blue ink on a textured
              map: two dots; a 40-mm route drawn in two pieces with a 6-mm skip; a 25-mm square outline with a
              3-mm gap; a hatched patch; "A2" written 6 mm from the first dot — and the model reporting A1 on
              those letters (with their label_box), B1 along the route, C1 and D1 roughly, and nothing for
              the second dot
        WHEN the marks are placed with the printed map as the reference
        THEN A1 is the first dot (within 0.5 mm), the route is ONE line spanning its 40 mm, the area a closed
             polygon 25 mm across, the patch a cloud of dots, all from the ink; the letters of "A2" become
             nothing; the second dot is A2, numbered by the reader and flagged doubtful
        """
        from PIL import ImageDraw, ImageFont
        from survey.paper import texture
        Question.objects.create(survey_section=self.s2, code='ROUTE', name='Route', input_type='line', order_number=2)
        Question.objects.create(survey_section=self.s2, code='ZONE', name='Zone', input_type='polygon', order_number=3)
        Question.objects.create(survey_section=self.s2, code='CLOUD', name='Cloud', input_type='spraycan', order_number=4)
        result = self.print_single()
        form = result.form
        map_page = next(int(n) for n, r in form.layout.items() if 'map' in r)
        rec = form.layout[str(map_page)]['map']
        img = self._image(_pdf_page_jpegs(result.pdf, [map_page - 1])[0])
        w, hgt = img.size
        x0, y0 = self._mm_to_px(rec['x_mm'], rec['y_mm'], img)
        x1, y1 = self._mm_to_px(rec['x_mm'] + rec['w_mm'], rec['y_mm'] + rec['h_mm'], img)
        ref = self._textured_map()
        img.paste(ref.resize((int(x1 - x0) - 6, int(y1 - y0) - 6)).convert('RGB'), (int(x0) + 3, int(y0) + 3))
        mm = w / marks.PAGE_MM['a4'][0]
        ink = (40, 60, 200)
        draw = ImageDraw.Draw(img)

        def at(fx, fy):
            return self._mm_to_px(rec['x_mm'] + fx * rec['w_mm'], rec['y_mm'] + fy * rec['h_mm'], img)
        dot = at(0.2, 0.25)
        draw.ellipse([dot[0] - mm, dot[1] - mm, dot[0] + mm, dot[1] + mm], fill=ink)
        draw.text((dot[0] + 6 * mm, dot[1] - 4 * mm), 'A2', fill=ink, font=ImageFont.load_default(size=int(7 * mm)))
        dot2 = at(0.5, 0.2)
        draw.ellipse([dot2[0] - mm, dot2[1] - mm, dot2[0] + mm, dot2[1] + mm], fill=ink)
        route = at(0.3, 0.6)
        draw.line([route, (route[0] + 17 * mm, route[1])], fill=ink, width=int(0.7 * mm))
        draw.line([(route[0] + 23 * mm, route[1]), (route[0] + 40 * mm, route[1] + 10 * mm)], fill=ink, width=int(0.7 * mm))
        sq = at(0.6, 0.45)
        corners = [sq, (sq[0] + 25 * mm, sq[1]), (sq[0] + 25 * mm, sq[1] + 25 * mm), (sq[0], sq[1] + 25 * mm)]
        draw.line(corners + [(sq[0], sq[1] + 3 * mm)], fill=ink, width=int(0.7 * mm))
        patch = at(0.75, 0.85)
        for k in range(8):
            draw.line([(patch[0] + 2 * k * mm, patch[1]), (patch[0] + 2 * k * mm + 3 * mm, patch[1] + 6 * mm)], fill=ink, width=int(0.8 * mm))
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=92)
        page = self.page_row(status='queued', printed_form=form, copy=None, page_number=map_page,
                             pages_total=form.pages, code_source='qr')
        page.image.save('ink.jpg', ContentFile(buf.getvalue()), save=True)
        rec, geo_items = extract.geo_items_for_page(page)
        self.assertEqual([(i['code'], i['letter']) for i in geo_items], [('WHERE', 'A'), ('ROUTE', 'B'), ('ZONE', 'C'), ('CLOUD', 'D')])

        def pt(x, y):
            return [y / hgt * 1000, x / w * 1000]
        label_centre = (dot[0] + 10 * mm, dot[1])
        raw = [
            {'label': 'A1', 'question': 'WHERE', 'points': [pt(*label_centre)], 'confidence': 0.9,
             'label_box': [pt(dot[0] + 6 * mm, dot[1] - 4 * mm)[0], pt(dot[0] + 6 * mm, dot[1] - 4 * mm)[1],
                           pt(dot[0] + 18 * mm, dot[1] + 3 * mm)[0], pt(dot[0] + 18 * mm, dot[1] + 3 * mm)[1]]},
            {'label': 'B1', 'question': 'ROUTE', 'points': [pt(route[0] + 5 * mm, route[1] + 2 * mm), pt(route[0] + 35 * mm, route[1] + 5 * mm)], 'confidence': 0.8},
            {'label': 'C1', 'question': 'ZONE', 'points': [pt(c[0] + 2 * mm, c[1] - 2 * mm) for c in corners], 'confidence': 0.8},
            {'label': 'D1', 'question': 'CLOUD', 'points': [pt(patch[0] - 2 * mm, patch[1] - 2 * mm), pt(patch[0] + 20 * mm, patch[1] + 8 * mm)], 'confidence': 0.8},
        ]
        out = marks.place_marks(raw, None, geo_items, rec, img, 'a4', reference=ref)
        west, south, east, north = rec['bbox']
        per_mm = ((east - west) / rec['w_mm'], (north - south) / rec['h_mm'])

        def frame_mm(lng, lat):
            return ((lng - west) / per_mm[0], (north - lat) / per_mm[1])
        where = out['WHERE']
        self.assertEqual(where['feature_labels'], ['A1', 'A2'])
        self.assertEqual(where['from_ink'], 2)
        a1, a2 = (frame_mm(*f['geometry']['coordinates']) for f in where['value'])
        self.assertAlmostEqual(a1[0], 0.2 * rec['w_mm'], delta=0.5)
        self.assertAlmostEqual(a1[1], 0.25 * rec['h_mm'], delta=0.5)
        self.assertAlmostEqual(a2[0], 0.5 * rec['w_mm'], delta=0.5)
        self.assertTrue(extract.is_doubtful(where))
        line = out['ROUTE']
        self.assertEqual((line['feature_labels'], line['from_ink']), (['B1'], 1))
        xs = [frame_mm(*c)[0] for c in line['value'][0]['geometry']['coordinates']]
        self.assertAlmostEqual(max(xs) - min(xs), 40.0, delta=6.0)   # the ends of a stroke on busy print are read a few mm short
        zone = out['ZONE']
        self.assertEqual((zone['feature_labels'], zone['from_ink']), (['C1'], 1))
        ring = zone['value'][0]['geometry']['coordinates'][0]
        xs = [frame_mm(*c)[0] for c in ring]
        ys = [frame_mm(*c)[1] for c in ring]
        self.assertAlmostEqual(max(xs) - min(xs), 25.0, delta=2.0)
        self.assertAlmostEqual(max(ys) - min(ys), 25.0, delta=2.0)
        cloud = out['CLOUD']
        self.assertEqual((cloud['feature_labels'], cloud['from_ink']), (['D1'], 1))
        self.assertEqual(cloud['value'][0]['geometry']['type'], 'MultiPoint')
        self.assertGreater(len(cloud['value'][0]['geometry']['coordinates']), 20)
        self.assertEqual(texture.REF_WIDTH, ref.width)

    def test_the_printed_map_is_kept_for_the_photos(self):
        """
        GIVEN a basemap the static map API serves
        WHEN the form is printed
        THEN the map page's record carries `ref_key` and no transient frame, the stored file is the frame at
             the matcher's width, and a page of that form reads it back; printed with the grid stand-in
             (no basemap), the record keeps no reference and the matcher gets none
        """
        from survey.models import _private_media_storage
        from survey.paper import texture
        from survey.print.static_map import FRAME_H, FRAME_W, SCALE
        self.assertNotIn('ref_key', self.rec)
        self.assertNotIn('_frame', self.rec)
        grid_page = self.page_row(status='queued', printed_form=self.form, copy=1, page_number=self.map_page,
                                  pages_total=self.form.pages, code_source='qr')
        with override_settings(MAPBOX_ACCESS_TOKEN=''):
            self.assertIsNone(texture.reference_image(grid_page))
        from survey.print.pdf import build_form
        with override_settings(MAPBOX_ACCESS_TOKEN='tok'), \
                mock.patch('survey.print.static_map.requests.get',
                           return_value=_response(200, _png(FRAME_W * SCALE, FRAME_H * SCALE))):
            result = build_form(self.survey, 'en', 'a4', user=self.owner, base_url='https://example.test')
        rec = result.form.layout[str(self.map_page)]['map']
        self.assertTrue(rec['ref_key'].startswith('paper_refs/'))
        self.assertNotIn('_frame', rec)
        self.assertTrue(_private_media_storage().exists(rec['ref_key']))
        page = self.page_row(status='queued', printed_form=result.form, copy=2, page_number=self.map_page,
                             pages_total=result.form.pages, code_source='qr')
        ref = texture.reference_image(page)
        self.assertEqual((ref.mode, ref.width), ('L', texture.REF_WIDTH))

    def test_frame_fractions_become_mercator_coordinates(self):
        """
        GIVEN the frame record of the map page
        WHEN its centre, its north-west corner and a point well outside it are placed
        THEN the centre is the frame's centre, the corner is the bbox's west/north, the outside point is None
        """
        west, south, east, north = self.rec['bbox']
        lng, lat = marks.mm_to_lnglat(self.rec['x_mm'] + self.rec['w_mm'] / 2, self.rec['y_mm'] + self.rec['h_mm'] / 2, self.rec)
        self.assertAlmostEqual(lng, (west + east) / 2, places=4)
        self.assertAlmostEqual(lat, self.s2.start_map_postion.y, places=3)
        lng, lat = marks.mm_to_lnglat(self.rec['x_mm'], self.rec['y_mm'], self.rec)
        self.assertAlmostEqual((lng, lat), (west, north), places=4)
        self.assertIsNone(marks.mm_to_lnglat(self.rec['x_mm'] - 20, self.rec['y_mm'], self.rec))

    def _page_with_render(self, sheet):
        page = self.page_row(sheet=sheet, status='queued', printed_form=self.form, copy=None,
                             page_number=self.map_page, pages_total=self.form.pages, code_source='qr')
        page.image.save('render.jpg', ContentFile(self.render), save=True)
        return page

    def _mark_at(self, fx, fy):
        """A model point ([y, x], 0..1000 of the photo) at a fraction of the frame."""
        x_mm = self.rec['x_mm'] + fx * self.rec['w_mm']
        y_mm = self.rec['y_mm'] + fy * self.rec['h_mm']
        return [y_mm / marks.PAGE_MM['a4'][1] * 1000, x_mm / marks.PAGE_MM['a4'][0] * 1000]

    def test_marks_become_features_with_their_row_answers(self):
        """
        GIVEN the model reports a dot A1 at the frame's centre with "shade" in its NOTE cell
        WHEN the page is extracted
        THEN the message named A = WHERE and the NOTE column, WHERE's value is one Point feature at the
             frame's centre whose properties carry NOTE, placed by the squares, and the field is confident
        """
        sheet = sheets_mod.new_sheet(self.inbox, printed_form=self.form)
        page = self._page_with_render(sheet)
        provider = _FakeProvider([{'fields': [], 'marks': [
            {'label': 'A1', 'question': 'WHERE', 'points': [self._mark_at(0.5, 0.5)], 'confidence': 0.9,
             'answers': [{'code': 'NOTE', 'value': 'shade'}]}]}])
        extraction, _usage, _items = extract.extract_page(page, provider)
        user = provider.requests[0]['user']
        self.assertIn('A = WHERE', user)
        self.assertIn('NOTE', user)
        field = extraction['WHERE']
        self.assertEqual(field['placement'], 'edges+squares')   # the fake provider draws no frame box: no fiducial search, but the frame's own border
        self.assertFalse(extract.is_doubtful(field))
        feature = field['value'][0]
        west, south, east, north = self.rec['bbox']
        self.assertEqual(feature['geometry']['type'], 'Point')
        self.assertAlmostEqual(feature['geometry']['coordinates'][0], (west + east) / 2, places=3)
        self.assertAlmostEqual(feature['geometry']['coordinates'][1], self.s2.start_map_postion.y, places=2)
        self.assertEqual(feature['properties'], {'question_id': 'WHERE', 'NOTE': ['shade']})

    def test_frame_box_stands_in_without_squares_and_nothing_without_both(self):
        """
        GIVEN a photo with no alignment squares in it
        WHEN the model reports the frame's box and a dot at its centre, and then no box at all
        THEN the dot is placed through the frame ("frame"); without the box the field is unreadable with the raw marks kept
        """
        blank = _jpeg(800, 1100)
        img = Image.open(io.BytesIO(blank))
        rec = self.rec
        frame_box = [200, 100, 600, 900]
        geo_items = [{'code': 'WHERE', 'type': 'point', 'name': 'Where?', 'letter': 'A', 'subs': []}]
        placed = marks.place_marks([{'label': 'A1', 'question': 'WHERE', 'points': [[400, 500]], 'confidence': 0.8}],
                                   frame_box, geo_items, rec, img, 'a4')
        self.assertEqual(placed['WHERE']['placement'], 'frame')
        west, south, east, north = rec['bbox']
        self.assertAlmostEqual(placed['WHERE']['value'][0]['geometry']['coordinates'][0], (west + east) / 2, places=3)
        self.assertEqual(placed['WHERE']['box'], frame_box)
        lost = marks.place_marks([{'label': 'A1', 'question': 'WHERE', 'points': [[400, 500]], 'confidence': 0.8}],
                                 None, geo_items, rec, img, 'a4')
        self.assertIsNone(lost['WHERE']['placement'])
        self.assertTrue(lost['WHERE']['unreadable'])
        self.assertEqual(lost['WHERE']['marks'][0]['label'], 'A1')

    def test_frame_corners_beat_the_frame_box_on_an_old_form(self):
        """
        GIVEN a photo at an angle of a form printed before the fiducials, cropped to the map
        WHEN the model reports the frame's four corners (a trapezoid) and a dot at the frame's centre
        THEN the dot lands at the frame's centre through the corners, where the axis-aligned box alone would miss
        """
        img = self._image(self.render)
        w, hgt = img.size
        src = [(0, 0), (w, 0), (0, hgt), (w, hgt)]
        dst = [(0.14 * w, 0.05 * hgt), (0.92 * w, 0.16 * hgt), (0.02 * w, 0.93 * hgt), (0.97 * w, 0.84 * hgt)]
        back = marks.homography(dst, src)
        coeffs = [back[0][0], back[0][1], back[0][2], back[1][0], back[1][1], back[1][2], back[2][0], back[2][1]]
        warped = img.transform((w, hgt), Image.PERSPECTIVE, coeffs, Image.BILINEAR, fillcolor=(70, 60, 50))
        forward = marks.homography(src, dst)
        rec = dict(self.rec)
        rec.pop('fiducials', None)
        rec.pop('fiducial_dx_mm', None)
        corners_mm = [(rec['x_mm'], rec['y_mm']), (rec['x_mm'] + rec['w_mm'], rec['y_mm']),
                      (rec['x_mm'], rec['y_mm'] + rec['h_mm']), (rec['x_mm'] + rec['w_mm'], rec['y_mm'] + rec['h_mm'])]
        wc = [marks.apply(forward, *self._mm_to_px(x, y, img)) for x, y in corners_mm]
        xs, ys = [c[0] for c in wc], [c[1] for c in wc]
        crop = (int(min(xs) - 60), int(min(ys) - 60), int(max(xs) + 60), int(max(ys) + 60))
        cropped = warped.crop(crop)
        cw, ch = cropped.size
        quad = [[(y - crop[1]) / ch * 1000, (x - crop[0]) / cw * 1000] for x, y in wc]
        frame_box = [min(p[0] for p in quad), min(p[1] for p in quad), max(p[0] for p in quad), max(p[1] for p in quad)]
        centre = marks.apply(forward, *self._mm_to_px(rec['x_mm'] + rec['w_mm'] / 2, rec['y_mm'] + rec['h_mm'] / 2, img))
        dot = [[(centre[1] - crop[1]) / ch * 1000, (centre[0] - crop[0]) / cw * 1000]]
        geo_items = [{'code': 'WHERE', 'type': 'point', 'name': 'Where?', 'letter': 'A', 'subs': []}]
        west, south, east, north = rec['bbox']
        with_corners = marks.place_marks([{'label': 'A1', 'question': 'WHERE', 'points': dot, 'confidence': 0.9}],
                                         frame_box, geo_items, rec, cropped, 'a4', frame_corners=quad)
        lng, lat = with_corners['WHERE']['value'][0]['geometry']['coordinates']
        self.assertEqual(with_corners['WHERE']['placement'], 'frame')
        self.assertAlmostEqual(lng, (west + east) / 2, delta=(east - west) * 0.01)
        self.assertAlmostEqual(lat, self.s2.start_map_postion.y, delta=(north - south) * 0.01)
        box_only = marks.place_marks([{'label': 'A1', 'question': 'WHERE', 'points': dot, 'confidence': 0.9}],
                                     frame_box, geo_items, rec, cropped, 'a4')
        lng_b, _lat_b = box_only['WHERE']['value'][0]['geometry']['coordinates']
        self.assertGreater(abs(lng_b - (west + east) / 2), abs(lng - (west + east) / 2))

    def test_shapes_from_vertices(self):
        """
        GIVEN vertices for each geo type
        WHEN geometries are built
        THEN a line needs two, an area three (closed), a cloud is dots inside the outline, a dot is the first vertex
        """
        a, b, c = (13.40, 52.50), (13.41, 52.50), (13.41, 52.51)
        self.assertEqual(marks.geometry_for('point', [a, b])['coordinates'], [13.40, 52.50])
        self.assertIsNone(marks.geometry_for('line', [a]))
        self.assertEqual(marks.geometry_for('line', [a, b])['type'], 'LineString')
        self.assertIsNone(marks.geometry_for('polygon', [a, b]))
        ring = marks.geometry_for('polygon', [a, b, c])['coordinates'][0]
        self.assertEqual((len(ring), ring[0], ring[-1]), (4, [13.40, 52.50], [13.40, 52.50]))
        cloud = marks.geometry_for('spraycan', [a, b, c])
        self.assertEqual(cloud['type'], 'MultiPoint')
        self.assertTrue(all(13.40 <= x <= 13.41 and 52.50 <= y <= 52.51 for x, y in cloud['coordinates']))

    def test_map_page_reads_like_the_paper_and_stores_the_rows(self):
        """
        GIVEN a response whose extraction holds a placed WHERE feature with its row answer
        WHEN the map page of the check renders
        THEN the page is half and half (form layout), the marks table names A = WHERE with the NOTE column,
             the page's map data carries the feature, its box and three printed rows, WHERE is no draw
             button, and the base map restores nothing;
        WHEN the page is posted with the hidden input the script fills
        THEN a point Answer with the NOTE sub-answer is stored and the next render shows the STORED row
        """
        feature = {'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [13.4, 52.5]},
                   'properties': {'question_id': 'WHERE', 'NOTE': ['shade']}}
        sheet = sheets_mod.new_sheet(self.inbox, printed_form=self.form)
        sheet.status = 'review'
        sheet.extraction = {'WHERE': {'value': [feature], 'confidence': 0.9, 'unreadable': False,
                                      'placement': 'squares', 'feature_boxes': [[300, 200, 400, 500]]}}
        sheet.save()
        self._page_with_render(sheet)
        self.client.post(self.url('paper_response_check', sheet.pk))
        url = self.url('paper_response_page', sheet.pk, self.map_page)
        html = self.client.get(url).content.decode()
        import html as html_lib
        import re
        self.assertIn('<body class="survey-form-layout"', html)
        self.assertIn('data-marks-question="WHERE"', html)
        self.assertIn('Why here?', html)
        self.assertNotIn('class="drawbutton', html)
        data = json.loads(html_lib.unescape(re.search(r'id="paper-map-data"[^>]*>(.*?)</script>', html, re.S).group(1)))
        q = data['questions'][0]
        self.assertEqual((q['code'], q['letter'], q['rows'], q['boxes']), ('WHERE', 'A', 3, [[300, 200, 400, 500]]))
        self.assertEqual(q['features'][0]['properties']['NOTE'], ['shade'])
        self.assertEqual(q['subs'][0]['code'], 'NOTE')
        self.assertEqual(data['bbox'], self.rec['bbox'])
        geo = json.loads(html_lib.unescape(re.search(r'id="geo-answers-data"[^>]*>(.*?)</script>', html, re.S).group(1)))
        self.assertEqual(geo, {})
        moved = dict(feature, properties={'question_id': 'WHERE', 'NOTE': ['shade, quiet']})
        moved['geometry'] = {'type': 'Point', 'coordinates': [13.41, 52.51]}
        self.client.post(url, {'WHERE': json.dumps(moved)})
        session = SurveySession.objects.get(paper_sheet=sheet)
        answer = Answer.objects.get(survey_session=session, question=self.where)
        self.assertAlmostEqual(answer.point.x, 13.41, places=5)
        self.assertEqual(Answer.objects.get(parent_answer_id=answer, question=self.note).text, 'shade, quiet')
        again = self.client.get(url).content.decode()
        data = json.loads(html_lib.unescape(re.search(r'id="paper-map-data"[^>]*>(.*?)</script>', again, re.S).group(1)))
        self.assertEqual(data['questions'][0]['features'][0]['geometry']['coordinates'], [13.41, 52.51])
        self.assertEqual(data['questions'][0]['features'][0]['properties']['NOTE'], ['shade, quiet'])

    def test_map_page_keeps_the_papers_order(self):
        """
        GIVEN a page whose items start with the end of section S1 (WHY) and then the heading of S2 with its map frame
        WHEN the page plan is built and the page renders
        THEN S1 comes before S2 in the plan, and on the page "About" precedes the marks block
        """
        from survey.paper_views import _page_plan
        self.form.layout = {'1': {'items': ['question:WHY', 'section:S2'], 'map': self.rec}}
        self.form.pages = 1
        self.form.save()
        sheet = sheets_mod.new_sheet(self.inbox, printed_form=self.form)
        header, plan = _page_plan(sheet, 1)
        self.assertEqual([(s.code, codes) for s, codes in plan], [('S1', ['WHY']), ('S2', ['WHERE'])])
        self._page_with_render(sheet)
        self.client.post(self.url('paper_response_check', sheet.pk))
        html = self.client.get(self.url('paper_response_page', sheet.pk, 1)).content.decode()
        about, marks, where = (html.index('paper-section-title">About</h3>'), html.index('id="paper-marks"'),
                              html.index('paper-section-title">Where</h3>'))
        self.assertLess(about, where)
        self.assertLess(where, marks)

    def test_printed_table_has_boxes_in_every_row(self):
        """
        GIVEN a choice sub-question of a map question
        WHEN the form is printed
        THEN every row of the marks table carries the options as boxes, and the header only the name
        """
        Question.objects.create(survey_section=self.s2, code='OFTEN', name='How often?', input_type='choice',
                                order_number=2, parent_question_id=self.where,
                                choices=[{'code': 1, 'name': 'daily'}, {'code': 2, 'name': 'weekly'}])
        from pypdf import PdfReader
        text = '\n'.join(p.extract_text() for p in PdfReader(io.BytesIO(self.print_single().pdf)).pages)
        self.assertGreaterEqual(text.count('daily'), 3)


# ── checking a response ────────────────────────────────────────────────────

class CheckTest(_PaperFixture):

    def setUp(self):
        super().setUp()
        self.form = PrintedForm.objects.create(
            survey=self.survey, version_number=1, language='en', structure_hash='h', pages=2,
            layout={'1': {'items': ['section:S1', 'question:ALB', 'question:WHY']},
                    '2': {'items': ['question:MOOD', 'section:S2', 'question:WHERE']}})

    def _sheet(self, extraction=None, pages=(1, 2)):
        sheet = PaperSheet.objects.create(batch=self.inbox, seq=self.inbox.next_sheet_seq, copy=37,
                                          printed_form=self.form, status='review', extraction=extraction or {})
        for n in pages:
            self.page_row(sheet=sheet, status='recognised', printed_form=self.form, copy=37, page_number=n,
                          pages_total=2, code_source='qr')
        return sheet

    def test_the_pane_carries_the_boxes_of_its_photo(self):
        """
        GIVEN page 1 of Copy 37 whose reading put ALB in a box
        WHEN page 1 of the check renders
        THEN the photo pane's page list carries that box under ALB (the form leads, the photo follows)
        """
        sheet = self._sheet({'ALB': _field('1')})
        PaperPage.objects.filter(sheet=sheet, page_number=1).update(
            extraction={'ALB': dict(_field('1'), box=[120, 40, 210, 880])})
        self.client.post(self.url('paper_response_check', sheet.pk))
        html = self.client.get(self.url('paper_response_page', sheet.pk, 1)).content.decode()
        import html as html_lib
        import re
        pages = json.loads(html_lib.unescape(re.search(r'data-paper-pages="([^"]*)"', html).group(1)))
        self.assertEqual(pages[0]['boxes'], {'ALB': [120, 40, 210, 880]})

    def test_check_starts_from_the_printed_form(self):
        """
        GIVEN Copy 37 of the printed form (version 1, English)
        WHEN the operator presses Check
        THEN a paper session on that version with the form's language and the link exists, no Answer
             rows exist, and page 1 renders its photo, its questions only, the stepper and the prefill
        """
        sheet = self._sheet({'ALB': _field('1'), 'WHY': _field('Too dark at night', 0.5)})
        response = self.client.post(self.url('paper_response_check', sheet.pk))
        session = SurveySession.objects.get(paper_sheet=sheet)
        self.assertEqual((session.survey, session.language, session.source, session.entered_by),
                         (self.survey, 'en', 'paper', self.owner))
        self.assertEqual(Answer.objects.count(), 0)
        self.assertRedirects(response, self.url('paper_response_page', sheet.pk, 1), fetch_redirect_response=False)
        page = self.client.get(response['Location'])
        self.assertContains(page, 'id="paper-pane"')
        self.assertContains(page, 'Copy 37')
        self.assertContains(page, 'name="goto" value="2"')
        import re
        radios = re.findall(r'<input[^>]*name="ALB"[^>]*>', page.content.decode())
        checked = [tag for tag in radios if 'checked' in tag]
        self.assertEqual(len(checked), 1, radios)
        self.assertIn('value="1"', checked[0])
        self.assertContains(page, 'Too dark at night')
        self.assertContains(page, 'data-paper-doubtful="WHY"')
        self.assertNotContains(page, 'name="MOOD"')

    def test_a_section_spanning_two_pages_keeps_both(self):
        """
        GIVEN section S1 spans pages 1 (ALB, WHY) and 2 (MOOD)
        WHEN page 1 is saved, then page 2 with MOOD only
        THEN page 2 shows MOOD beside the map section's question, the save after page 2 leaves
             ALB and WHY stored, and Finish lands on the Saved page
        """
        sheet = self._sheet({'ALB': _field('1'), 'WHY': _field('dark'), 'MOOD': _field(['1'])})
        self.client.post(self.url('paper_response_check', sheet.pk))
        session = SurveySession.objects.get(paper_sheet=sheet)
        first = self.client.post(self.url('paper_response_page', sheet.pk, 1), {'ALB': '1', 'WHY': 'dark'})
        self.assertRedirects(first, self.url('paper_response_page', sheet.pk, 2), fetch_redirect_response=False)
        second = self.client.get(first['Location'])
        self.assertContains(second, 'name="MOOD"')
        self.assertContains(second, 'Where?')
        self.assertNotContains(second, 'name="WHY"')
        done = self.client.post(self.url('paper_response_page', sheet.pk, 2), {'MOOD': ['1']})
        self.assertRedirects(done, reverse('operator_entry_saved', args=[self.survey.uuid, session.pk]),
                             fetch_redirect_response=False)
        stored = {a.question.code: a for a in Answer.objects.filter(survey_session=session).select_related('question')}
        self.assertEqual(sorted(stored), ['ALB', 'MOOD', 'WHY'])

    def test_stepper_jumps_and_saves(self):
        """
        GIVEN page 1 of a check
        WHEN the operator presses stepper page 2
        THEN page 1's answers are saved and page 2 opens
        """
        sheet = self._sheet()
        self.client.post(self.url('paper_response_check', sheet.pk))
        response = self.client.post(self.url('paper_response_page', sheet.pk, 1), {'ALB': '0', 'goto': '2'})
        self.assertRedirects(response, self.url('paper_response_page', sheet.pk, 2), fetch_redirect_response=False)
        self.assertTrue(Answer.objects.filter(question=self.alb).exists())

    def test_missing_page_is_attached_from_the_check(self):
        """
        GIVEN Copy 37 with page 1 only
        WHEN the operator opens page 2 and attaches a photo whose code will not read
        THEN the pane offers the attach box, the status says missing, and after the upload the page lands
             on this response as page 2 (code_source manual), is read, and the status says recognised
        """
        sheet = self._sheet({'ALB': _field('1')}, pages=(1,))
        sheet.status = 'incomplete'
        sheet.save()
        self.client.post(self.url('paper_response_check', sheet.pk))
        page = self.client.get(self.url('paper_response_page', sheet.pk, 2))
        self.assertContains(page, 'paper-attach')
        self.assertContains(page, 'was not photographed')
        status = self.url('paper_response_page_status', sheet.pk, 2)
        self.assertEqual(json.loads(self.client.get(status).content)['state'], 'missing')
        provider = _FakeProvider([{'fields': [{'code': 'MOOD', 'value': ['1'], 'confidence': 0.9, 'unreadable': False}]}])
        self.upload(_jpeg(), name='p2.jpg', sheet=sheet, page_number=2, provider=provider)
        attached = sheet.pages.get(page_number=2)
        self.assertEqual((attached.status, attached.code_source, attached.copy), ('recognised', 'manual', 37))
        self.assertEqual(json.loads(self.client.get(status).content)['state'], 'recognised')
        sheet.refresh_from_db()
        self.assertEqual(sheet.extraction['MOOD']['value'], ['1'])
        again = self.client.get(self.url('paper_response_page', sheet.pk, 2))
        self.assertNotContains(again, 'paper-attach')

    def test_old_form_without_items_falls_back_to_the_section_flow(self):
        """
        GIVEN a PrintedForm printed before the item map existed
        WHEN the operator presses Check
        THEN the section flow of the operator entry form opens, with the photo pane
        """
        self.form.layout = {}
        self.form.save()
        sheet = self._sheet({'ALB': _field('1')})
        response = self.client.post(self.url('paper_response_check', sheet.pk))
        session = SurveySession.objects.get(paper_sheet=sheet)
        self.assertRedirects(response, reverse('operator_entry_section', args=[self.survey.uuid, session.pk, 'about']),
                             fetch_redirect_response=False)
        self.assertContains(self.client.get(response['Location']), 'id="paper-pane"')

    def test_stored_photos_gone_event_counts_and_next(self):
        """
        GIVEN Copy 37 read as ALB=1 (doubtful), WHY=dark, and Copy 38 complete and read
        WHEN the operator corrects WHY, finishes Copy 37 and reaches the Saved page
        THEN the session is completed, the response stored, its photos gone, paper_sheet_entered carries
             2 / 1 / 1, and the Saved page offers Check Copy 38
        """
        import posthog
        sheet = self._sheet({'ALB': _field('1', 0.5), 'WHY': _field('dark')})
        other = PaperSheet.objects.create(batch=self.inbox, seq=self.inbox.next_sheet_seq + 1, copy=38,
                                          printed_form=self.form, status='review')
        self.page_row(sheet=other, status='recognised', printed_form=self.form, copy=38, page_number=1)
        with _eager_tasks():
            self.client.post(self.url('paper_response_check', sheet.pk))
            session = SurveySession.objects.get(paper_sheet=sheet)
            self.client.post(self.url('paper_response_page', sheet.pk, 1), {'ALB': '1', 'WHY': 'very dark'})
            self.client.post(self.url('paper_response_page', sheet.pk, 2), {})
            with mock.patch.object(posthog, 'disabled', False), mock.patch('posthog.capture') as capture:
                saved = self.client.get(reverse('operator_entry_saved', args=[self.survey.uuid, session.pk]))
        session.refresh_from_db()
        sheet.refresh_from_db()
        self.assertIsNotNone(session.end_datetime)
        self.assertEqual(sheet.status, 'entered')
        self.assertTrue(all(not p.image for p in sheet.pages.all()))
        props = [c for c in capture.call_args_list if c.args[0] == 'paper_sheet_entered'][0].kwargs['properties']
        self.assertEqual((props['fields_total'], props['fields_doubtful'], props['fields_changed']), (2, 1, 1))
        self.assertContains(saved, 'Copy 37 stored')
        self.assertContains(saved, 'Check Copy 38')

    def test_a_reshot_page_replaces_the_answers_the_operator_did_not_touch(self):
        """
        GIVEN page 1 read as ALB=1, WHY="dark", the operator pressed Next (ALB and WHY stored as read)
              and then changed WHY to "too dark" and saved again
        WHEN page 1 is photographed again and read as ALB=0, WHY="darker"
        THEN the untouched ALB row is gone (the page now prefills 0) and the operator's WHY stays
        """
        from survey import tasks
        sheet = self._sheet({'ALB': _field('1'), 'WHY': _field('dark')}, pages=(1,))
        old_page = sheet.pages.get(page_number=1)
        PaperPage.objects.filter(pk=old_page.pk).update(extraction={'ALB': _field('1'), 'WHY': _field('dark')})
        self.client.post(self.url('paper_response_check', sheet.pk))
        url = self.url('paper_response_page', sheet.pk, 1)
        self.client.post(url, {'ALB': '1', 'WHY': 'dark'})
        self.client.post(url, {'ALB': '1', 'WHY': 'too dark'})
        new_page = self.page_row(sheet=sheet, status='queued', printed_form=self.form, copy=37, page_number=1,
                                 pages_total=2, code_source='qr')
        PaperPage.objects.filter(pk=old_page.pk).update(status='replaced')
        provider = _FakeProvider([{'fields': [
            {'code': 'ALB', 'value': '0', 'confidence': 0.9, 'unreadable': False},
            {'code': 'WHY', 'value': 'darker', 'confidence': 0.9, 'unreadable': False}]}])
        with mock.patch('survey.ai.client.get_provider', return_value=provider):
            tasks.recognise_paper_page(new_page.pk)
        session = SurveySession.objects.get(paper_sheet=sheet)
        self.assertFalse(Answer.objects.filter(survey_session=session, question=self.alb).exists())
        self.assertEqual(Answer.objects.get(survey_session=session, question=self.why).text, 'too dark')
        import re
        html = self.client.get(url).content.decode()
        radio = re.search(r'<input[^>]*name="ALB"[^>]*value="0"[^>]*>', html)
        self.assertIsNotNone(radio)
        self.assertIn('checked', radio.group(0))

    def test_delete(self):
        """
        GIVEN Copy 37 being checked (a session, pages with photos)
        WHEN the operator deletes it
        THEN its pages, photos and row are gone, the session is trashed, and a new photo of copy 37 makes
             Copy 37 anew instead of being set aside; a stored response cannot be deleted here
        """
        sheet = self._sheet({'ALB': _field('1')})
        with _eager_tasks():
            self.client.post(self.url('paper_response_check', sheet.pk))
            session = SurveySession.objects.get(paper_sheet=sheet)
            response = self.client.post(self.url('paper_response_delete', sheet.pk))
        self.assertRedirects(response, self.url('paper_home'), fetch_redirect_response=False)
        self.assertFalse(PaperSheet.objects.filter(pk=sheet.pk).exists())
        self.assertFalse(PaperPage.objects.filter(sheet_id=sheet.pk).exists())
        session.refresh_from_db()
        self.assertTrue(session.is_deleted)
        result = self.print_copies(40)
        self.upload(_pdf_page_jpegs(result.pdf, [36 * result.form.pages])[0])
        again = PaperSheet.objects.get(copy=37)
        self.assertEqual((again.status != 'entered', again.pages.count()), (True, 1))
        stored = sheets_mod.new_sheet(self.inbox, copy=38, printed_form=self.form)
        PaperSheet.objects.filter(pk=stored.pk).update(status='entered')
        self.client.post(self.url('paper_response_delete', stored.pk))
        self.assertTrue(PaperSheet.objects.filter(pk=stored.pk).exists())

    def test_image_is_gated(self):
        """
        GIVEN a viewer
        WHEN they request a page image URL
        THEN the response is 403; the owner gets the JPEG
        """
        page = self.page_row(status='recognised')
        viewer = User.objects.create_user('paper_viewer2', password='pass')
        Membership.objects.create(user=viewer, organization=self.org, role='viewer')
        self.login(viewer)
        self.assertEqual(self.client.get(self.url('paper_page_image', page.pk)).status_code, 403)
        self.login(self.owner)
        response = self.client.get(self.url('paper_page_image', page.pk))
        self.assertEqual((response.status_code, response['Content-Type']), (200, 'image/jpeg'))

    def test_typed_in_session_is_unchanged(self):
        """
        GIVEN a session entered through the header (no paper response)
        WHEN its section renders
        THEN no photo pane and no prefill data are in the response
        """
        response = self.client.post(reverse('operator_entry_header', args=[self.survey.uuid]),
                                    {'source': 'paper', 'version': self.survey.pk, 'language': 'en'})
        page = self.client.get(response['Location'])
        self.assertNotContains(page, 'paper-pane')
        self.assertNotContains(page, 'data-paper-doubtful')

    def test_drawer_and_export_name_the_copy(self):
        """
        GIVEN a session stored from Copy 37
        WHEN the drawer opens and the workbook is exported
        THEN the drawer says Copy 37 and the sessions sheet carries paper_copy 37
        """
        import openpyxl
        sheet = self._sheet({'ALB': _field('1')})
        self.client.post(self.url('paper_response_check', sheet.pk))
        session = SurveySession.objects.get(paper_sheet=sheet)
        Answer.objects.create(survey_session=session, question=self.alb, selected_choices=[1])
        session.mark_completed()
        drawer = self.client.get(reverse('analytics_session_detail', args=[self.survey.uuid, session.pk]))
        self.assertContains(drawer, 'Copy 37')
        response = self.client.get(f'/surveys/{self.survey.uuid}/download?format=xlsx')
        wb = openpyxl.load_workbook(io.BytesIO(b''.join(response.streaming_content)))
        rows = list(wb['sessions'].iter_rows(values_only=True))
        self.assertEqual(dict(zip(rows[0], rows[1]))['paper_copy'], 37)


# ── lifetime, layout ───────────────────────────────────────────────────────

class SweepTest(_PaperFixture):

    def test_sweep_deletes_stale_open_responses_and_keeps_stored_ones(self):
        """
        GIVEN a response last touched 31 days ago with a photo, a fresh one, and a stored one as old
        WHEN sweep_paper_batches runs dry, then with --delete
        THEN the dry run deletes nothing; the real run deletes the stale open response whole (row, page,
             photo) and leaves the fresh and the stored ones
        """
        stale = sheets_mod.new_sheet(self.inbox)
        page = self.page_row(sheet=stale, status='recognised', page_number=1)
        fresh = sheets_mod.new_sheet(self.inbox)
        fresh_page = self.page_row(sheet=fresh, status='recognised', page_number=1)
        stored = sheets_mod.new_sheet(self.inbox)
        old = timezone.now() - timezone.timedelta(days=31)
        PaperSheet.objects.filter(pk__in=[stale.pk, stored.pk]).update(last_activity_at=old)
        PaperSheet.objects.filter(pk=stored.pk).update(status='entered')
        out = io.StringIO()
        call_command('sweep_paper_batches', stdout=out)
        page.refresh_from_db()
        self.assertTrue(page.image)
        self.assertIn('would be deleted', out.getvalue())
        call_command('sweep_paper_batches', '--delete', stdout=out)
        self.assertFalse(PaperSheet.objects.filter(pk=stale.pk).exists())
        self.assertFalse(PaperPage.objects.filter(pk=page.pk).exists())
        fresh_page.refresh_from_db()
        self.assertTrue(fresh_page.image)
        self.assertTrue(PaperSheet.objects.filter(pk=stored.pk).exists())

    def test_trust_page_states_the_retention(self):
        """
        GIVEN the trust page
        WHEN it renders
        THEN it says photographs of paper forms are deleted once stored or after 30 days
        """
        page = self.client.get('/trust/')
        self.assertContains(page, 'Photos of paper forms')
        self.assertContains(page, 'after 30 days')


class LayoutItemsTest(_PaperFixture):

    def test_layout_lists_the_items_of_every_page(self):
        """
        GIVEN the printed form
        WHEN its layout is read
        THEN page 1 lists section S1 and its questions in order, and WHERE is listed on exactly one page
             at or after the page that starts section S2, which also records the map frame
        """
        layout = self.print_single().form.layout
        self.assertEqual(layout['1']['items'][:4], ['section:S1', 'question:ALB', 'question:WHY', 'question:MOOD'])
        section_pages = [k for k, v in layout.items() if 'section:S2' in v.get('items', [])]
        question_pages = [k for k, v in layout.items() if 'question:WHERE' in v.get('items', [])]
        self.assertEqual((len(section_pages), len(question_pages)), (1, 1))
        self.assertLessEqual(int(section_pages[0]), int(question_pages[0]))
        self.assertTrue(any('map' in v for v in layout.values()))
