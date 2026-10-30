"""Tests for the `paper-photo-entry` capability (openspec/changes/paper-photo-entry/specs/paper-photo-entry/spec.md).

Change paper-photo-entry (#495, epic #350 item 3): photos or scans of filled paper forms become
prefilled operator entries. The model is a fake provider; the QR path is real — a form printed by
`build_form` is rendered to pixels with pypdfium2 and read back with zxing-cpp, which is the whole
ingest + code pipeline end to end, offline.
"""
import io
import json
from contextlib import contextmanager
from unittest import mock

from django.contrib.auth.models import User
from django.contrib.gis.geos import Point
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from billing.tests.helpers import make_sub
from survey.ai.client import ProviderError
from survey.models import (
    AIGenerationEvent, Answer, Membership, Organization, PaperBatch, PaperPage, PaperSheet, PaperUpload,
    PrintedForm, Question, SurveyHeader, SurveySection, SurveySession,
)
from survey.paper import extract, sheets as sheets_mod
from survey.paper.ingest import ingest_upload, sniff
from survey.tests.helpers import _FakeProvider


def _jpeg(width=400, height=560, color=(255, 255, 255)):
    buf = io.BytesIO()
    Image.new('RGB', (width, height), color).save(buf, format='JPEG')
    return buf.getvalue()


def _field(value, confidence=0.95, unreadable=False):
    return {'value': value, 'confidence': confidence, 'unreadable': unreadable}


@contextmanager
def _eager_tasks():
    """The views enqueue Celery tasks; the suite has no broker, so `.delay` runs the task."""
    from survey import tasks
    # The views import the Task objects themselves, so patching `.delay` on the
    # module's objects reaches every caller.
    with mock.patch.object(tasks.ingest_paper_upload, 'delay', side_effect=lambda pk: tasks.ingest_paper_upload(pk)), \
            mock.patch.object(tasks.recognise_paper_page, 'delay', side_effect=lambda pk: tasks.recognise_paper_page(pk)), \
            mock.patch.object(tasks.delete_sheet_images, 'delay', side_effect=lambda pk: tasks.delete_sheet_images(pk)):
        yield


class _PaperFixture(TestCase):
    """A Pro workspace, a two-section survey (choice + text, then a point), its printed form."""

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
        with override_settings(MAPBOX_ACCESS_TOKEN=''):
            from survey.print.pdf import build_form
            self.printed = build_form(self.survey, 'en', 'a4', user=self.owner, base_url='https://example.test')
        self.form = self.printed.form

    def login(self, user):
        self.client.force_login(user)
        s = self.client.session
        s['active_org_id'] = self.org.id
        s.save()

    def new_batch(self):
        return PaperBatch.objects.create(survey=self.survey, organization=self.org, created_by=self.owner)

    def page_images(self):
        """The printed form rendered to page JPEGs, through the real splitter."""
        from survey.paper.ingest import iter_pages
        return [jpeg for jpeg, _w, _h in iter_pages(self.printed.pdf, 'pdf')]

    def add_page(self, batch, jpeg=None, **fields):
        upload = PaperUpload.objects.create(batch=batch, seq=batch.next_upload_seq, original_name='x.jpg', status='split')
        batch.next_upload_seq += 1
        page = PaperPage(batch=batch, upload=upload, seq=batch.next_page_seq, width=400, height=560, **fields)
        batch.next_page_seq += 1
        batch.save()
        page.image.save('p.jpg', ContentFile(jpeg or _jpeg()), save=False)
        page.save()
        return page

    def url(self, name, *args):
        return reverse(name, args=[self.survey.uuid, *args])


# ── gate and batch pages ───────────────────────────────────────────────────

class BatchGateTest(_PaperFixture):

    def test_editor_of_pro_workspace_opens_a_batch(self):
        """
        GIVEN an owner of a Pro workspace
        WHEN they open the batches page and press New batch
        THEN a PaperBatch exists for the canonical survey and its page renders the drop zone
        """
        self.assertEqual(self.client.get(self.url('paper_batches')).status_code, 200)
        response = self.client.post(self.url('paper_batch_new'))
        batch = PaperBatch.objects.get()
        self.assertEqual(batch.survey, self.survey)
        self.assertRedirects(response, self.url('paper_batch', batch.pk))
        page = self.client.get(self.url('paper_batch', batch.pk))
        self.assertContains(page, 'id="paper-drop"')

    def test_viewer_cannot(self):
        """
        GIVEN a workspace viewer
        WHEN they request the batches page
        THEN the response is 403
        """
        viewer = User.objects.create_user('paper_viewer', password='pass')
        Membership.objects.create(user=viewer, organization=self.org, role='viewer')
        self.login(viewer)
        self.assertEqual(self.client.get(self.url('paper_batches')).status_code, 403)

    def test_free_workspace_sees_the_refusal(self):
        """
        GIVEN a workspace without Pro
        WHEN an owner requests the batches page
        THEN the response is the feature refusal
        """
        self.sub.delete()
        response = self.client.get(self.url('paper_batches'))
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, 'billing/feature_required.html')

    def test_another_surveys_batch_is_404(self):
        """
        GIVEN a batch of a different survey
        WHEN it is requested under this survey's URL
        THEN the response is 404
        """
        other = SurveyHeader.objects.create(name='other', organization=self.org, created_by=self.owner, redirect_url='#')
        batch = PaperBatch.objects.create(survey=other, organization=self.org, created_by=self.owner)
        self.assertEqual(self.client.get(self.url('paper_batch', batch.pk)).status_code, 404)

    def test_responses_offers_from_photos(self):
        """
        GIVEN a Pro workspace
        WHEN Responses renders
        THEN the Enter a response dropdown links to the batches page
        """
        page = self.client.get(reverse('editor_survey_analytics', args=[self.survey.uuid]))
        self.assertContains(page, self.url('paper_batches'))


class UploadTest(_PaperFixture):

    def _post(self, batch, name='a.jpg', data=None, size=None):
        data = data if data is not None else _jpeg()
        fh = io.BytesIO(data)
        fh.name = name
        from django.core.files.uploadedfile import SimpleUploadedFile
        return self.client.post(self.url('paper_upload', batch.pk),
                                {'file': SimpleUploadedFile(name, data, content_type='application/octet-stream')})

    def test_files_land_in_order_and_are_queued(self):
        """
        GIVEN an open batch
        WHEN three files are posted
        THEN three PaperUpload rows exist with seq 1..3 and the ingest task is enqueued for each
        """
        batch = self.new_batch()
        from survey import tasks
        with mock.patch.object(tasks.ingest_paper_upload, 'delay') as delay, self.captureOnCommitCallbacks(execute=True):
            for name in ('a.jpg', 'b.jpg', 'c.jpg'):
                response = self._post(batch, name)
                self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(list(batch.uploads.values_list('seq', flat=True)), [1, 2, 3])
        self.assertEqual(delay.call_count, 3)
        self.assertEqual(batch.uploads.first().status, 'queued')
        self.assertTrue(batch.uploads.first().file)

    @override_settings(PAPER_UPLOAD_MAX_BYTES=1000)
    def test_file_too_large(self):
        """
        GIVEN a 40 KB file and a 1 KB limit
        WHEN it is posted
        THEN the response is 413 and nothing is stored
        """
        batch = self.new_batch()
        response = self._post(batch, data=b'x' * 40000)
        self.assertEqual(response.status_code, 413)
        self.assertEqual(batch.uploads.count(), 0)

    def test_closed_batch_refuses(self):
        """
        GIVEN a closed batch
        WHEN a file is posted
        THEN the response is 409
        """
        batch = self.new_batch()
        batch.status = 'closed'
        batch.save()
        self.assertEqual(self._post(batch).status_code, 409)
        self.assertEqual(batch.uploads.count(), 0)

    def test_status_endpoint(self):
        """
        GIVEN a batch with one queued page and one sheet in review
        WHEN the status endpoint is polled
        THEN it answers in_flight true with the counts
        """
        batch = self.new_batch()
        self.add_page(batch, status='queued')
        sheet = PaperSheet.objects.create(batch=batch, seq=1, printed_form=self.form, status='review')
        self.add_page(batch, sheet=sheet, status='recognised', printed_form=self.form, page_number=1)
        data = json.loads(self.client.get(self.url('paper_batch_status', batch.pk)).content)
        self.assertTrue(data['in_flight'])
        self.assertEqual(data['pages_open'], 1)
        self.assertEqual(data['sheets'], {'review': 1})


# ── ingest ─────────────────────────────────────────────────────────────────

class IngestTest(_PaperFixture):

    def _upload(self, batch, data, name='scan.pdf'):
        upload = PaperUpload.objects.create(batch=batch, seq=batch.next_upload_seq, original_name=name, size=len(data))
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

    def test_pdf_is_split_into_pages_and_the_original_deleted(self):
        """
        GIVEN the printed form as a PDF
        WHEN it is ingested
        THEN one PaperPage per page exists with a JPEG, the upload is split and its file gone
        """
        batch = self.new_batch()
        upload = self._upload(batch, self.printed.pdf)
        created = ingest_upload(upload)
        upload.refresh_from_db()
        self.assertEqual(created, self.printed.pages)
        self.assertEqual(upload.status, 'split')
        self.assertFalse(upload.file)
        pages = list(batch.pages.order_by('seq'))
        self.assertEqual([p.seq for p in pages], list(range(1, self.printed.pages + 1)))
        with pages[0].image.open('rb') as fh:
            self.assertTrue(fh.read(3).startswith(b'\xff\xd8'))

    def test_not_a_document(self):
        """
        GIVEN a .docx
        WHEN it is ingested
        THEN the upload is failed with "Not a photo or PDF", no page exists and the file is deleted
        """
        batch = self.new_batch()
        upload = self._upload(batch, b'PK\x03\x04' + b'\x00' * 100, name='notes.docx')
        ingest_upload(upload)
        upload.refresh_from_db()
        self.assertEqual(upload.status, 'failed')
        self.assertEqual(upload.error, 'Not a photo or PDF')
        self.assertEqual(batch.pages.count(), 0)
        self.assertFalse(upload.file)

    def test_big_photo_is_bounded_and_exif_upright(self):
        """
        GIVEN a 6000 x 4000 photo with an EXIF rotation of 90 degrees
        WHEN it is ingested
        THEN the stored page is at most 2200 px on its long side and upright (portrait)
        """
        img = Image.new('RGB', (6000, 4000), (200, 200, 200))
        exif = img.getexif()
        exif[0x0112] = 6   # orientation: rotate 90 CW
        buf = io.BytesIO()
        img.save(buf, format='JPEG', exif=exif.tobytes())
        batch = self.new_batch()
        upload = self._upload(batch, buf.getvalue(), name='IMG_1.jpg')
        ingest_upload(upload)
        page = batch.pages.get()
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
        batch = self.new_batch()
        upload = self._upload(batch, buf.getvalue(), name='IMG_2.heic')
        ingest_upload(upload)
        page = batch.pages.get()
        with page.image.open('rb') as fh:
            self.assertTrue(fh.read(3).startswith(b'\xff\xd8'))

    def test_ingest_is_idempotent(self):
        """
        GIVEN an upload already split
        WHEN the task runs again
        THEN no second set of pages is created
        """
        batch = self.new_batch()
        upload = self._upload(batch, self.printed.pdf)
        ingest_upload(upload)
        upload.refresh_from_db()
        ingest_upload(upload)
        self.assertEqual(batch.pages.count(), self.printed.pages)


# ── codes and placement ────────────────────────────────────────────────────

class CodeTest(_PaperFixture):

    def test_qr_round_trips_from_the_printed_form(self):
        """
        GIVEN the printed form rendered to page images
        WHEN each page's QR is decoded locally
        THEN it names the PrintedForm, the page number and the page count
        """
        from survey.paper.codes import decode_qr
        images = self.page_images()
        for number, jpeg in enumerate(images, start=1):
            parsed = decode_qr(jpeg)
            self.assertIsNotNone(parsed, f'page {number} QR not read')
            self.assertEqual(parsed, (self.form.pk, number, len(images)))

    def test_footer_text_fallback_through_the_model(self):
        """
        GIVEN a page whose QR cannot be read
        WHEN recognition runs with a provider that reads the footer text
        THEN the page gets its code with code_source text, and the call is accounted as paper_code
        """
        from survey import tasks
        batch = self.new_batch()
        page = self.add_page(batch)
        provider = _FakeProvider([{'code': f'MS-{self.form.code}-1'}, {'fields': []}])
        with mock.patch('survey.ai.client.get_provider', return_value=provider):
            tasks.recognise_paper_page(page.pk)
        page.refresh_from_db()
        self.assertEqual((page.printed_form_id, page.page_number, page.code_source), (self.form.pk, 1, 'text'))
        self.assertEqual(page.status, 'recognised')
        self.assertEqual(AIGenerationEvent.objects.filter(kind='paper_code', outcome='success').count(), 1)

    def test_someone_elses_form_is_unrecognised(self):
        """
        GIVEN a page carrying the code of another survey's printed form
        WHEN recognition runs
        THEN the page is unrecognised and nothing is extracted
        """
        from survey import tasks
        other = SurveyHeader.objects.create(name='other', organization=self.org, created_by=self.owner, redirect_url='#')
        foreign = PrintedForm.objects.create(survey=other, version_number=1, language='en', structure_hash='x', pages=1)
        batch = self.new_batch()
        page = self.add_page(batch)
        provider = _FakeProvider([{'code': f'MS-{foreign.code}-1'}])
        with mock.patch('survey.ai.client.get_provider', return_value=provider):
            tasks.recognise_paper_page(page.pk)
        page.refresh_from_db()
        self.assertEqual(page.status, 'unrecognised')
        self.assertEqual(page.extraction, {})
        self.assertEqual(len(provider.calls), 1)
        listing = self.client.get(self.url('paper_batch', batch.pk))
        self.assertContains(listing, 'Not recognised')
        self.assertContains(listing, self.url('paper_page_assign', batch.pk, page.pk))

    def test_assigned_by_hand(self):
        """
        GIVEN an unrecognised page
        WHEN the operator assigns it to the printed form, page 1
        THEN it is recognised as if its code had read so
        """
        from survey import tasks
        batch = self.new_batch()
        page = self.add_page(batch, status='unrecognised')
        provider = _FakeProvider([{'fields': [{'code': 'ALB', 'value': '1', 'confidence': 0.9, 'unreadable': False}]}])
        with mock.patch('survey.ai.client.get_provider', return_value=provider), _eager_tasks(), \
                self.captureOnCommitCallbacks(execute=True):
            self.client.post(self.url('paper_page_assign', batch.pk, page.pk), {'form': self.form.pk, 'page_number': 1})
        page.refresh_from_db()
        self.assertEqual((page.status, page.code_source, page.page_number), ('recognised', 'manual', 1))
        self.assertEqual(page.extraction['ALB']['value'], '1')


class PlacementTest(_PaperFixture):

    def _recognised(self, batch, number, total=3, form=None):
        return self.add_page(batch, status='recognised', printed_form=form or self.form,
                             page_number=number, pages_total=total, code_source='qr')

    def test_sheets_of_three_pages_in_order(self):
        """
        GIVEN pages 1, 2, 3, 1, 2, 3 of the same form recognised in seq order
        WHEN placement runs
        THEN two sheets exist, each in review with pages 1..3
        """
        batch = self.new_batch()
        for n in (1, 2, 3, 1, 2, 3):
            self._recognised(batch, n)
        sheets_mod.place_pages(batch)
        rows = list(batch.sheets.order_by('seq'))
        self.assertEqual([s.status for s in rows], ['review', 'review'])
        for sheet in rows:
            self.assertEqual(sorted(sheet.pages.values_list('page_number', flat=True)), [1, 2, 3])

    def test_a_missing_page_makes_an_incomplete_sheet(self):
        """
        GIVEN pages 1, 2, 1, 2, 3
        WHEN placement runs
        THEN the first sheet is incomplete (page 3 missing) and the second is review
        """
        batch = self.new_batch()
        for n in (1, 2, 1, 2, 3):
            self._recognised(batch, n)
        sheets_mod.place_pages(batch)
        first, second = batch.sheets.order_by('seq')
        self.assertEqual(first.status, 'incomplete')
        self.assertEqual(sheets_mod.missing_pages(first), [3])
        self.assertEqual(second.status, 'review')

    def test_out_of_order_completion_waits(self):
        """
        GIVEN page seq 2 recognised before page seq 1
        WHEN placement runs
        THEN nothing is placed until page 1 is recognised, then both are placed in order
        """
        batch = self.new_batch()
        first = self.add_page(batch, status='queued')
        self._recognised(batch, 2)
        sheets_mod.place_pages(batch)
        self.assertEqual(batch.sheets.count(), 0)
        first.status, first.printed_form, first.page_number, first.pages_total = 'recognised', self.form, 1, 3
        first.save()
        sheets_mod.place_pages(batch)
        sheet = batch.sheets.get()
        self.assertEqual(sorted(sheet.pages.values_list('page_number', flat=True)), [1, 2])

    def test_moved_page_stays(self):
        """
        GIVEN a page moved to a new sheet by the operator
        WHEN more pages are recognised and placed
        THEN the moved page remains on its sheet
        """
        batch = self.new_batch()
        p1 = self._recognised(batch, 1)
        p2 = self._recognised(batch, 2)
        sheets_mod.place_pages(batch)
        moved = sheets_mod.move_page(p2, None)
        self._recognised(batch, 3)
        sheets_mod.place_pages(batch)
        p1.refresh_from_db()
        p2.refresh_from_db()
        self.assertEqual(p2.sheet_id, moved.pk)
        self.assertTrue(p2.pinned)
        self.assertEqual(p1.sheet.pages.count(), 1)

    def test_duplicate_page_starts_an_incomplete_sheet(self):
        """
        GIVEN pages 1, 2, 2, 3
        WHEN placement runs
        THEN the second page 2 starts a new sheet flagged incomplete
        """
        batch = self.new_batch()
        for n in (1, 2, 2, 3):
            self._recognised(batch, n)
        sheets_mod.place_pages(batch)
        rows = list(batch.sheets.order_by('seq'))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].status, 'incomplete')
        self.assertEqual(rows[1].status, 'incomplete')


# ── extraction ─────────────────────────────────────────────────────────────

class ExtractionTest(_PaperFixture):

    def _page(self, number=1, layout_items=None):
        batch = self.new_batch()
        if layout_items is not None:
            self.form.layout = {str(number): {'items': layout_items}}
            self.form.save()
        return self.add_page(batch, status='queued', printed_form=self.form, page_number=number,
                             pages_total=self.form.pages, code_source='qr')

    def test_items_bounded_by_the_page(self):
        """
        GIVEN page 1 holds ALB and WHY, page 2 holds the point question
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
        self.assertEqual(len(request['images']), 1)
        self.assertEqual(request['images'][0][0], 'image/jpeg')
        self.assertIn('1 = Yes', request['user'])
        self.assertNotIn('WHERE', request['user'])
        self.assertEqual(extraction['ALB']['value'], '1')
        self.assertEqual(extraction['WHY']['value'], 'Too dark at night')
        self.assertNotIn('WHERE', extraction)

    def test_geo_is_never_asked_and_whole_form_fallback(self):
        """
        GIVEN a PrintedForm whose layout has no items map
        WHEN a page of it is extracted
        THEN the whole structure is sent minus the geo question, with the "only what the page shows" instruction
        """
        page = self._page(2)
        self.form.layout = {}
        self.form.save()
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

    def test_doubtful_count_and_merge(self):
        """
        GIVEN two pages, the first with WHY at confidence 0.4 and the second repeating ALB
        WHEN the sheet is merged
        THEN the earlier page's ALB wins and doubtful_count is 1
        """
        batch = self.new_batch()
        sheet = PaperSheet.objects.create(batch=batch, seq=1, printed_form=self.form)
        self.add_page(batch, sheet=sheet, status='recognised', printed_form=self.form, page_number=1,
                      extraction={'ALB': _field('1'), 'WHY': _field('dark', 0.4)})
        self.add_page(batch, sheet=sheet, status='recognised', printed_form=self.form, page_number=2,
                      extraction={'ALB': _field('0')})
        sheets_mod.refresh_sheet(sheet)
        sheet.refresh_from_db()
        self.assertEqual(sheet.extraction['ALB']['value'], '1')
        self.assertEqual(sheet.doubtful_count, 1)

    def test_provider_down_marks_the_page_failed_and_costs_it(self):
        """
        GIVEN a provider that answers a transient error every time
        WHEN the page task runs out of retries
        THEN the page is failed, the list offers Retry, no Answer exists, and every call is accounted
        """
        from survey import tasks
        page = self._page(1, ['question:ALB'])
        provider = _FakeProvider([], error=ProviderError('API error 503: busy', transient=True))
        with mock.patch('survey.ai.client.get_provider', return_value=provider), \
                mock.patch('survey.paper.codes.decode_qr', return_value=(self.form.pk, 1, 2)):
            # Eager apply runs the retries inline: the first attempt plus PAPER_PAGE_RETRIES more.
            tasks.recognise_paper_page.apply(args=(page.pk,), retries=0, throw=False)
        self.assertEqual(len(provider.calls), tasks.PAPER_PAGE_RETRIES + 1)
        page.refresh_from_db()
        self.assertEqual(page.status, 'failed')
        self.assertEqual(Answer.objects.count(), 0)
        events = AIGenerationEvent.objects.filter(kind='paper_page')
        self.assertGreaterEqual(events.count(), 1)
        self.assertTrue(all(e.outcome == 'provider_error' for e in events))
        listing = self.client.get(self.url('paper_batch', page.batch_id))
        self.assertContains(listing, 'Retry')

    def test_event_and_posthog_generation_per_call(self):
        """
        GIVEN a page with a readable QR
        WHEN it is recognised
        THEN one AIGenerationEvent(paper_page, success) exists and one $ai_generation was captured
             with span paper_page, trace paper-batch-<id>, the token counts and no content
        """
        import posthog
        from survey import tasks
        page = self._page(1, ['question:ALB'])
        provider = _FakeProvider([{'fields': [{'code': 'ALB', 'value': '1', 'confidence': 0.9, 'unreadable': False}]}])
        with mock.patch('survey.ai.client.get_provider', return_value=provider), \
                mock.patch('survey.paper.codes.decode_qr', return_value=(self.form.pk, 1, 2)), \
                mock.patch.object(posthog, 'disabled', False), \
                mock.patch('posthog.capture') as capture:
            tasks.recognise_paper_page(page.pk)
        event = AIGenerationEvent.objects.get(kind='paper_page')
        self.assertEqual((event.outcome, event.organization, event.input_tokens), ('success', self.org, 100))
        generations = [c for c in capture.call_args_list if c.args[0] == '$ai_generation']
        self.assertEqual(len(generations), 1)
        props = generations[0].kwargs['properties']
        self.assertEqual(props['$ai_span_name'], 'paper_page')
        self.assertEqual(props['$ai_trace_id'], f'paper-batch-{page.batch_id}')
        self.assertEqual(props['$ai_input_tokens'], 100)
        self.assertEqual(props['batch_id'], page.batch_id)
        self.assertFalse(any('Albino' in str(v) or 'value' in str(k) for k, v in props.items()))
        recognised = [c for c in capture.call_args_list if c.args[0] == 'paper_page_recognised']
        self.assertEqual(recognised[0].kwargs['properties']['outcome'], 'recognised')
        self.assertEqual(recognised[0].kwargs['properties']['code_source'], 'qr')


# ── review ─────────────────────────────────────────────────────────────────

class ReviewTest(_PaperFixture):

    def _sheet(self, extraction=None, pages=(1, 2)):
        batch = self.new_batch()
        sheet = PaperSheet.objects.create(batch=batch, seq=1, printed_form=self.form, status='review',
                                          extraction=extraction or {}, doubtful_count=0)
        for n in pages:
            self.add_page(batch, sheet=sheet, status='recognised', printed_form=self.form, page_number=n,
                          pages_total=len(pages), code_source='qr')
        return batch, sheet

    def test_review_starts_from_the_form_code(self):
        """
        GIVEN a sheet of the printed form (version 1, English)
        WHEN the operator presses Review
        THEN a paper session on that version with the form's language and the sheet link exists,
             no Answer rows exist, and the first entry section renders with the page pane
        """
        batch, sheet = self._sheet({'ALB': _field('1'), 'WHY': _field('Too dark at night', 0.5)})
        response = self.client.post(self.url('paper_sheet_enter', batch.pk, sheet.pk))
        session = SurveySession.objects.get(paper_sheet=sheet)
        self.assertEqual((session.survey, session.language, session.source, session.entered_by),
                         (self.survey, 'en', 'paper', self.owner))
        self.assertEqual(Answer.objects.count(), 0)
        self.assertRedirects(response, reverse('operator_entry_section', args=[self.survey.uuid, session.pk, 's1'])
                             .replace('/s1/', '/about/'), fetch_redirect_response=False)
        page = self.client.get(response['Location'])
        self.assertContains(page, 'id="paper-pane"')
        import re
        html = page.content.decode()
        radios = re.findall(r'<input[^>]*name="ALB"[^>]*>', html)
        checked = [tag for tag in radios if 'checked' in tag]
        self.assertEqual(len(checked), 1, radios)
        self.assertIn('value="1"', checked[0])
        self.assertContains(page, 'Too dark at night')
        self.assertContains(page, 'data-paper-doubtful="WHY"')
        self.assertContains(page, 'fields to check')

    def test_saved_rows_win_and_blank_is_marked(self):
        """
        GIVEN the operator changed WHY and saved the section, and MOOD was read blank
        WHEN the section is opened again
        THEN the field shows the saved text and MOOD is listed as blank
        """
        batch, sheet = self._sheet({'ALB': _field('1'), 'WHY': _field('dark'), 'MOOD': _field(None, 1.0)})
        self.client.post(self.url('paper_sheet_enter', batch.pk, sheet.pk))
        session = SurveySession.objects.get(paper_sheet=sheet)
        url = reverse('operator_entry_section', args=[self.survey.uuid, session.pk, 'about'])
        self.client.post(url, {'ALB': '1', 'WHY': 'very dark'})
        page = self.client.get(url)
        self.assertContains(page, 'very dark')
        self.assertNotContains(page, '>dark<')
        self.assertContains(page, 'data-paper-blank="MOOD"')

    def test_page_pane_follows_the_section(self):
        """
        GIVEN a two-page form whose page 2 items include section S2
        WHEN section S2 renders
        THEN the pane shows page 2 and a switcher over both pages
        """
        batch, sheet = self._sheet({'ALB': _field('1')})
        self.form.layout = {'1': {'items': ['section:S1', 'question:ALB']}, '2': {'items': ['section:S2', 'question:WHERE']}}
        self.form.save()
        self.client.post(self.url('paper_sheet_enter', batch.pk, sheet.pk))
        session = SurveySession.objects.get(paper_sheet=sheet)
        page2 = sheet.pages.get(page_number=2)
        page = self.client.get(reverse('operator_entry_section', args=[self.survey.uuid, session.pk, 'where']))
        self.assertContains(page, f'data-paper-current="{page2.pk}"')
        self.assertEqual(len(json.loads(page.context['paper_pages'] and json.dumps(page.context['paper_pages']))), 2)

    def test_image_is_gated(self):
        """
        GIVEN a viewer
        WHEN they request a page image URL
        THEN the response is 403
        """
        batch, sheet = self._sheet()
        page = sheet.pages.first()
        viewer = User.objects.create_user('paper_viewer2', password='pass')
        Membership.objects.create(user=viewer, organization=self.org, role='viewer')
        self.login(viewer)
        self.assertEqual(self.client.get(self.url('paper_page_image', batch.pk, page.pk)).status_code, 403)
        self.login(self.owner)
        response = self.client.get(self.url('paper_page_image', batch.pk, page.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/jpeg')

    def test_typed_in_session_is_unchanged(self):
        """
        GIVEN a session entered through the header (no sheet)
        WHEN its section renders
        THEN no page pane and no prefill data are in the response
        """
        response = self.client.post(reverse('operator_entry_header', args=[self.survey.uuid]),
                                    {'source': 'paper', 'version': self.survey.pk, 'language': 'en'})
        page = self.client.get(response['Location'])
        self.assertNotContains(page, 'paper-pane')
        self.assertNotContains(page, 'data-paper-doubtful')

    def test_entered_sheet_images_gone_and_event_counts(self):
        """
        GIVEN a sheet whose extraction read ALB=1 (doubtful) and WHY=dark
        WHEN the operator corrects WHY, saves both sections and reaches the Saved page
        THEN the session is completed, the sheet entered, its images gone, and paper_sheet_entered
             carries fields_total 2, fields_doubtful 1, fields_changed 1
        """
        import posthog
        batch, sheet = self._sheet({'ALB': _field('1', 0.5), 'WHY': _field('dark')})
        with _eager_tasks():
            self.client.post(self.url('paper_sheet_enter', batch.pk, sheet.pk))
            session = SurveySession.objects.get(paper_sheet=sheet)
            self.client.post(reverse('operator_entry_section', args=[self.survey.uuid, session.pk, 'about']),
                             {'ALB': '1', 'WHY': 'very dark'})
            self.client.post(reverse('operator_entry_section', args=[self.survey.uuid, session.pk, 'where']), {})
            with mock.patch.object(posthog, 'disabled', False), mock.patch('posthog.capture') as capture:
                saved = self.client.get(reverse('operator_entry_saved', args=[self.survey.uuid, session.pk]))
        self.assertEqual(saved.status_code, 200)
        session.refresh_from_db()
        sheet.refresh_from_db()
        self.assertIsNotNone(session.end_datetime)
        self.assertEqual(sheet.status, 'entered')
        self.assertTrue(all(not p.image for p in sheet.pages.all()))
        entered = [c for c in capture.call_args_list if c.args[0] == 'paper_sheet_entered']
        props = entered[0].kwargs['properties']
        self.assertEqual((props['fields_total'], props['fields_doubtful'], props['fields_changed']), (2, 1, 1))
        self.assertContains(saved, 'No more sheets to review')

    def test_next_sheet_opens_the_following_one(self):
        """
        GIVEN a batch with two sheets in review
        WHEN the first is entered
        THEN the Saved page's Next sheet posts to the second sheet's review
        """
        batch, first = self._sheet({'ALB': _field('1')})
        second = PaperSheet.objects.create(batch=batch, seq=2, printed_form=self.form, status='review')
        with _eager_tasks():
            self.client.post(self.url('paper_sheet_enter', batch.pk, first.pk))
            session = SurveySession.objects.get(paper_sheet=first)
            saved = self.client.get(reverse('operator_entry_saved', args=[self.survey.uuid, session.pk]))
        self.assertContains(saved, self.url('paper_sheet_enter', batch.pk, second.pk))

    def test_skip(self):
        """
        GIVEN a sheet with an empty session
        WHEN the operator skips it
        THEN the sheet is skipped, its images gone and the session trashed
        """
        batch, sheet = self._sheet({'ALB': _field('1')})
        with _eager_tasks():
            self.client.post(self.url('paper_sheet_enter', batch.pk, sheet.pk))
            self.client.post(self.url('paper_sheet_skip', batch.pk, sheet.pk))
        sheet.refresh_from_db()
        self.assertEqual(sheet.status, 'skipped')
        self.assertTrue(all(not p.image for p in sheet.pages.all()))
        self.assertTrue(SurveySession.objects.get(paper_sheet=sheet).is_deleted)

    def test_drawer_and_export_name_the_sheet(self):
        """
        GIVEN a session entered from sheet 1 of a batch
        WHEN the drawer opens and the workbook is exported
        THEN the drawer says "Sheet 1 of batch N" and the sessions sheet carries paper_batch / paper_sheet
        """
        import openpyxl
        batch, sheet = self._sheet({'ALB': _field('1')})
        self.client.post(self.url('paper_sheet_enter', batch.pk, sheet.pk))
        session = SurveySession.objects.get(paper_sheet=sheet)
        Answer.objects.create(survey_session=session, question=self.alb, selected_choices=[1])
        session.mark_completed()
        drawer = self.client.get(reverse('analytics_session_detail', args=[self.survey.uuid, session.pk]))
        self.assertContains(drawer, f'Sheet 1 of batch {batch.pk}')
        response = self.client.get(f'/surveys/{self.survey.uuid}/download?format=xlsx')
        body = b''.join(response.streaming_content)
        wb = openpyxl.load_workbook(io.BytesIO(body))
        rows = list(wb['sessions'].iter_rows(values_only=True))
        header = list(rows[0])
        row = dict(zip(header, rows[1]))
        self.assertEqual((row['paper_batch'], row['paper_sheet']), (batch.pk, 1))


# ── lifetime ───────────────────────────────────────────────────────────────

class SweepTest(_PaperFixture):

    def test_sweep_closes_stale_batches_and_keeps_rows(self):
        """
        GIVEN a batch last touched 31 days ago with a sheet in review, and a fresh one
        WHEN sweep_paper_batches runs dry, then with --delete
        THEN the dry run deletes nothing; the real run closes the stale batch, deletes its images, keeps its rows
        """
        stale = self.new_batch()
        sheet = PaperSheet.objects.create(batch=stale, seq=1, printed_form=self.form, status='review')
        page = self.add_page(stale, sheet=sheet, status='recognised', printed_form=self.form, page_number=1)
        PaperBatch.objects.filter(pk=stale.pk).update(last_activity_at=timezone.now() - timezone.timedelta(days=31))
        fresh = self.new_batch()
        fresh_page = self.add_page(fresh, status='recognised', printed_form=self.form, page_number=1)
        out = io.StringIO()
        call_command('sweep_paper_batches', stdout=out)
        page.refresh_from_db()
        self.assertTrue(page.image)
        self.assertIn('would be closed', out.getvalue())
        call_command('sweep_paper_batches', '--delete', stdout=out)
        stale.refresh_from_db()
        page.refresh_from_db()
        fresh_page.refresh_from_db()
        self.assertEqual(stale.status, 'closed')
        self.assertFalse(page.image)
        self.assertTrue(fresh_page.image)
        self.assertTrue(PaperSheet.objects.filter(pk=sheet.pk).exists())
        self.assertTrue(PaperPage.objects.filter(pk=page.pk).exists())

    def test_trust_page_states_the_retention(self):
        """
        GIVEN the trust page
        WHEN it renders
        THEN it says photographs of paper forms are deleted once stored or after 30 days
        """
        page = self.client.get('/trust/')
        self.assertContains(page, 'Photos of paper forms')
        self.assertContains(page, 'after 30 days')


# ── printed form items ─────────────────────────────────────────────────────

class LayoutItemsTest(_PaperFixture):

    def test_layout_lists_the_items_of_every_page(self):
        """
        GIVEN the printed form
        WHEN its layout is read
        THEN page 1 lists section S1 and its questions in order, and the map page lists section S2
        """
        layout = self.form.layout
        first = layout['1']['items']
        self.assertEqual(first[:4], ['section:S1', 'question:ALB', 'question:WHY', 'question:MOOD'])
        section_pages = [k for k, v in layout.items() if 'section:S2' in v.get('items', [])]
        question_pages = [k for k, v in layout.items() if 'question:WHERE' in v.get('items', [])]
        self.assertEqual(len(section_pages), 1)
        self.assertEqual(len(question_pages), 1)
        self.assertLessEqual(int(section_pages[0]), int(question_pages[0]))
        self.assertTrue(any('map' in v for v in layout.values()))
