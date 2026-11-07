"""Landing pages (spec `survey-landings`, change landing-core, #576; epic #348) and the
landing half of `abuse-review` (one review table for surveys and landings)."""
import json
from datetime import timedelta
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from billing.models import STATUS_FINISHED
from billing.tests.helpers import make_sub, trial_used_elsewhere
from survey import landings
from survey.content_screening import confirm_phishing
from survey.models import (ContentReview, Landing, LandingBlock, LandingSurvey, Membership, Organization,
                           PublicResultsPage, SurveyHeader)


def _png():
    from PIL import Image
    buf = BytesIO()
    Image.new('RGB', (4, 4), (200, 10, 10)).save(buf, 'PNG')
    return SimpleUploadedFile('cover.png', buf.getvalue(), content_type='image/png')


class LandingTestBase(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Riverside', slug='riverside')
        self.owner = User.objects.create_user('lp_owner', 'owner@example.test', 'pass')
        self.editor = User.objects.create_user('lp_editor', 'editor@example.test', 'pass')
        self.viewer = User.objects.create_user('lp_viewer', 'viewer@example.test', 'pass')
        Membership.objects.create(user=self.owner, organization=self.org, role='owner')
        Membership.objects.create(user=self.editor, organization=self.org, role='editor')
        Membership.objects.create(user=self.viewer, organization=self.org, role='viewer')
        self.sub = make_sub(self.org)
        self.survey = SurveyHeader.objects.create(name='park_survey', organization=self.org,
                                                  created_by=self.owner, status='published')
        self.landing = Landing.objects.create(organization=self.org, title='Riverside Park plan',
                                              slug='riverside-park-plan', created_by=self.owner)

    def login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def url(self, name, *args):
        return reverse(name, args=[self.landing.uuid, *args])

    def add_block(self, kind, **fields):
        return self.client.post(self.url('editor_landing_block_add'), dict(kind=kind, **fields))

    def _every_kind(self):
        self.add_block('text', body='<p>About the park</p>', title='About')
        self.add_block('image', alt='Park', image=_png())
        self.add_block('button', label='Read the plan', url='https://city.example/plan')
        self.add_block('video', url='https://vimeo.com/123456789')
        self.client.post(self.url('editor_landing_block_add'), {'kind': 'faq', 'q': ['Q?'], 'a': ['<p>A</p>']})
        self.client.post(self.url('editor_landing_block_add'), {
            'kind': 'timeline', 'phase_title': ['Now'], 'phase_when': ['2027'], 'phase_body': [''], 'current': '0'})
        self.add_block('survey', survey=self.survey.uuid, title='Take part')
        self.assertEqual(self.landing.blocks.count(), 7)


class LandingEntityTest(LandingTestBase):
    def test_editor_creates_landing(self):
        """GIVEN an editor of a Pro workspace
        WHEN they post a title to create a landing
        THEN a draft landing with a slug from the title exists and the builder opens"""
        self.login(self.editor)
        r = self.client.post(reverse('editor_landing_create'), {'title': 'Old Town square'})
        landing = Landing.objects.get(title='Old Town square')
        self.assertRedirects(r, reverse('editor_landing', args=[landing.uuid]), fetch_redirect_response=False)
        self.assertEqual(landing.slug, 'old-town-square')
        self.assertFalse(landing.is_published)
        self.assertEqual(landing.organization, self.org)

    def test_slug_from_taken_title_gets_a_suffix(self):
        """GIVEN a landing already holds the slug riverside-park-plan
        WHEN another landing is created with the same title
        THEN its slug carries a numeric suffix"""
        self.assertEqual(landings.unique_slug('Riverside Park plan'), 'riverside-park-plan-2')

    def test_viewer_cannot_change(self):
        """GIVEN a viewer of the workspace
        WHEN they post settings, a block or publish
        THEN every response is 403 and nothing changes"""
        self.login(self.viewer)
        self.assertEqual(self.client.post(self.url('editor_landing_settings'),
                                          {'title': 'X', 'slug': 'xxx'}).status_code, 403)
        self.assertEqual(self.add_block('text', body='<p>Hi</p>').status_code, 403)
        self.assertEqual(self.client.post(self.url('editor_landing_publish'), {'action': 'publish'}).status_code, 403)
        self.landing.refresh_from_db()
        self.assertEqual(self.landing.title, 'Riverside Park plan')
        self.assertFalse(self.landing.blocks.exists())

    def test_viewer_sees_builder_read_only(self):
        """GIVEN a viewer
        WHEN they open the builder
        THEN it renders without the Add block button"""
        self.login(self.viewer)
        r = self.client.get(self.url('editor_landing'))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'id="landing-add-block"')

    def test_other_workspace_gets_404(self):
        """GIVEN a member of another workspace
        WHEN they open this landing's builder
        THEN the response is 404"""
        other = Organization.objects.create(name='Other', slug='other')
        stranger = User.objects.create_user('stranger', 's@example.test', 'pass')
        Membership.objects.create(user=stranger, organization=other, role='owner')
        self.client.force_login(stranger)
        self.assertEqual(self.client.get(self.url('editor_landing')).status_code, 404)

    def test_slug_rules(self):
        """GIVEN the settings form
        WHEN the slug is reserved, too short or taken
        THEN the save is refused with a field error and the slug stays"""
        Landing.objects.create(organization=self.org, title='Other', slug='taken-slug')
        self.login(self.editor)
        for bad in ('edit', 'ab', 'taken-slug', 'Bad Slug'):
            r = self.client.post(self.url('editor_landing_settings'), {'title': 'T', 'slug': bad})
            self.assertEqual(r.status_code, 400, bad)
        self.landing.refresh_from_db()
        self.assertEqual(self.landing.slug, 'riverside-park-plan')

    def test_settings_save_with_cover(self):
        """GIVEN an editor
        WHEN they save a summary, an unlisted visibility, a language and a cover
        THEN the landing keeps them and the cover is stored under a random key"""
        self.login(self.editor)
        r = self.client.post(self.url('editor_landing_settings'), {
            'title': 'Riverside Park', 'summary': 'Tell us  what you think.', 'slug': 'riverside',
            'language': 'de', 'visibility': 'unlisted', 'cover': _png(), 'cover_alt': 'The park'})
        self.assertEqual(r.status_code, 302)
        self.landing.refresh_from_db()
        self.assertEqual((self.landing.slug, self.landing.language, self.landing.visibility),
                         ('riverside', 'de', 'unlisted'))
        self.assertEqual(self.landing.summary, 'Tell us what you think.')
        self.assertTrue(self.landing.cover.name.startswith('landing_assets/'))
        self.assertNotIn('cover', self.landing.cover.name.split('/')[-1])


class LandingSurveyLinkTest(LandingTestBase):
    def test_one_survey_on_two_landings(self):
        """GIVEN two landings of the workspace
        WHEN an editor links the same survey to both
        THEN both list it"""
        second = Landing.objects.create(organization=self.org, title='Transport', slug='transport')
        self.login(self.editor)
        for landing in (self.landing, second):
            self.client.post(reverse('editor_landing_survey_link', args=[landing.uuid]), {'survey': self.survey.uuid})
        self.assertEqual(LandingSurvey.objects.filter(survey=self.survey).count(), 2)

    def test_foreign_survey_refused(self):
        """GIVEN a survey of another workspace
        WHEN an editor tries to link it
        THEN the response is 404 and nothing is linked"""
        other = Organization.objects.create(name='Other', slug='other')
        foreign = SurveyHeader.objects.create(name='foreign', organization=other)
        self.login(self.editor)
        r = self.client.post(self.url('editor_landing_survey_link'), {'survey': foreign.uuid})
        self.assertEqual(r.status_code, 404)
        self.assertFalse(LandingSurvey.objects.exists())

    def test_archived_or_trashed_survey_refused(self):
        """GIVEN an archived and a trashed survey of the workspace
        WHEN an editor tries to link them
        THEN both are refused"""
        archived = SurveyHeader.objects.create(name='old', organization=self.org, status='archived')
        trashed = SurveyHeader.objects.create(name='gone', organization=self.org, deleted_at=timezone.now())
        self.login(self.editor)
        for s in (archived, trashed):
            self.assertEqual(self.client.post(self.url('editor_landing_survey_link'), {'survey': s.uuid}).status_code, 404)

    def test_draft_copy_links_canonical(self):
        """GIVEN a draft copy of a published survey
        WHEN it is linked
        THEN the canonical survey is linked"""
        draft = SurveyHeader.objects.create(name='park_survey', organization=self.org, published_version=self.survey)
        self.login(self.editor)
        self.client.post(self.url('editor_landing_survey_link'), {'survey': draft.uuid})
        self.assertEqual(list(self.landing.survey_links.values_list('survey', flat=True)), [self.survey.pk])

    def test_unlinking_removes_cards(self):
        """GIVEN a landing with a card for survey S
        WHEN S is unlinked
        THEN the card is gone too"""
        self.login(self.editor)
        self.add_block('survey', survey=self.survey.uuid)
        link = self.landing.survey_links.get()
        self.assertEqual(self.landing.blocks.count(), 1)
        self.client.post(self.url('editor_landing_survey_unlink', link.pk))
        self.assertFalse(self.landing.blocks.exists())


class LandingBlockTest(LandingTestBase):
    def setUp(self):
        super().setUp()
        self.login(self.editor)

    def test_text_is_sanitised(self):
        """GIVEN a text block with a script
        WHEN it is saved
        THEN the script is gone"""
        self.add_block('text', body='<p>Hello</p><script>alert(1)</script>')
        body = self.landing.blocks.get().data['body']
        self.assertIn('<p>Hello</p>', body)
        self.assertNotIn('script', body)

    def test_plain_text_body_is_escaped(self):
        """GIVEN a text block posted as plain text with an angle bracket
        WHEN it is saved
        THEN it is kept as text, not dropped as an unknown tag"""
        self.add_block('text', body='takes <5 minutes')
        self.assertIn('&lt;5 minutes', self.landing.blocks.get().data['body'])

    def test_unsafe_button_refused(self):
        """GIVEN a button with a javascript: URL
        WHEN it is saved
        THEN the save is refused with the URL error"""
        r = self.add_block('button', label='Go', url='javascript:alert(1)')
        self.assertEqual(r.status_code, 400)
        self.assertContains(r, 'Enter a full web address', status_code=400)
        self.assertFalse(self.landing.blocks.exists())

    def test_video_only_youtube_or_vimeo(self):
        """GIVEN a YouTube short link and a link to another host
        WHEN video blocks are saved
        THEN the first stores the player URL and the second is refused"""
        self.add_block('video', url='https://youtu.be/dQw4w9WgXcQ')
        self.assertEqual(self.landing.blocks.get().data['embed'], 'https://www.youtube.com/embed/dQw4w9WgXcQ')
        r = self.add_block('video', url='https://evil.example/video')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.landing.blocks.count(), 1)

    def test_faq_and_timeline(self):
        """GIVEN FAQ and timeline forms with parallel row lists
        WHEN they are saved
        THEN the items keep their order and the current phase index"""
        self.client.post(self.url('editor_landing_block_add'), {
            'kind': 'faq', 'q': ['Who decides?', 'When?'], 'a': ['<p>The council.</p>', '']})
        self.client.post(self.url('editor_landing_block_add'), {
            'kind': 'timeline', 'phase_title': ['Survey', 'Draft plan', 'Decision'],
            'phase_when': ['March 2027', 'May', 'Autumn'], 'phase_body': ['', '', ''], 'current': '1'})
        faq, timeline = self.landing.blocks.order_by('order')
        self.assertEqual([i['q'] for i in faq.data['items']], ['Who decides?', 'When?'])
        self.assertEqual(timeline.data['current'], 1)
        self.assertEqual(len(timeline.data['items']), 3)

    def test_clean_block_drops_unknown_keys_and_caps(self):
        """GIVEN raw data with unknown keys and an overlong caption
        WHEN clean_block runs
        THEN only the kind's keys remain, capped"""
        data, errors = landings.clean_block('image', {'caption': 'x' * 900, 'evil': 1})
        self.assertEqual(set(data), {'alt', 'caption'})
        self.assertEqual(len(data['caption']), 300)
        self.assertEqual(errors, {})

    def test_image_block_needs_a_picture(self):
        """GIVEN an image block without a file
        WHEN it is added
        THEN it is refused; with a file it is stored under a random key"""
        self.assertEqual(self.add_block('image', alt='Park').status_code, 400)
        self.add_block('image', alt='Park', image=_png())
        self.assertTrue(self.landing.blocks.get().image.name.startswith('landing_assets/'))

    def test_reorder(self):
        """GIVEN three blocks
        WHEN the full id list is posted in a new order
        THEN orders follow it; a list naming another landing's block is refused"""
        for i in range(3):
            self.add_block('text', body=f'<p>{i}</p>')
        ids = list(self.landing.blocks.order_by('order').values_list('id', flat=True))
        r = self.client.post(self.url('editor_landing_blocks_reorder'), json.dumps({'order': ids[::-1]}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(list(self.landing.blocks.order_by('order').values_list('id', flat=True)), ids[::-1])
        other = Landing.objects.create(organization=self.org, title='O', slug='other-page')
        foreign = LandingBlock.objects.create(landing=other, kind='text', data={'body': '<p>x</p>'})
        r = self.client.post(self.url('editor_landing_blocks_reorder'),
                             json.dumps({'order': ids[:2] + [foreign.pk]}), content_type='application/json')
        self.assertEqual(r.status_code, 400)

    def test_edit_and_delete(self):
        """GIVEN a text block
        WHEN it is edited and then deleted
        THEN the body changes and then the block is gone"""
        self.add_block('text', body='<p>One</p>')
        block = self.landing.blocks.get()
        self.client.post(self.url('editor_landing_block_edit', block.pk), {'body': '<p>Two</p>', 'title': 'About'})
        block.refresh_from_db()
        self.assertEqual((block.title, block.data['body']), ('About', '<p>Two</p>'))
        self.client.post(self.url('editor_landing_block_delete', block.pk))
        self.assertFalse(self.landing.blocks.exists())

    def test_builder_renders_every_kind(self):
        """GIVEN a landing with one block of every kind
        WHEN the builder and the add form of every kind render
        THEN all answer 200"""
        self._every_kind()
        self.assertEqual(self.client.get(self.url('editor_landing')).status_code, 200)
        for kind in landings.BLOCK_KINDS:
            self.assertEqual(self.client.get(self.url('editor_landing') + f'?add={kind}').status_code, 200, kind)

class SurveyCardTest(LandingTestBase):
    def card(self):
        return landings.survey_card(SurveyHeader.objects.get(pk=self.survey.pk))

    def test_open(self):
        """GIVEN a published survey without a period
        WHEN its card is drawn
        THEN it is open with the survey's URL"""
        card = self.card()
        self.assertEqual(card['state'], 'open')
        self.assertTrue(card['url'].endswith(f'/surveys/{self.survey.uuid}/'))

    def test_before_period(self):
        """GIVEN a published survey that opens next week
        WHEN its card is drawn
        THEN it is upcoming with the date and no link"""
        SurveyHeader.objects.filter(pk=self.survey.pk).update(opens_at=timezone.now() + timedelta(days=7))
        card = self.card()
        self.assertEqual((card['state'], card['url']), ('upcoming', ''))
        self.assertIsNotNone(card['opens_at'])

    def test_closed_with_results(self):
        """GIVEN a closed survey with a published public results page
        WHEN its card is drawn
        THEN it is closed and links to /r/<slug>/"""
        SurveyHeader.objects.filter(pk=self.survey.pk).update(status='closed')
        PublicResultsPage.objects.create(survey=self.survey, slug='park-results', is_published=True)
        card = self.card()
        self.assertEqual(card['state'], 'closed')
        self.assertTrue(card['results_url'].endswith('/r/park-results/'))

    def test_draft(self):
        """GIVEN a draft survey
        WHEN its card is drawn
        THEN it is coming soon with no link"""
        SurveyHeader.objects.filter(pk=self.survey.pk).update(status='draft')
        card = self.card()
        self.assertEqual((card['state'], card['url'], card['opens_at']), ('upcoming', '', None))

    def test_archived_card_not_drawn(self):
        """GIVEN a card for a survey that is later archived
        WHEN the public page renders
        THEN the card is not on it"""
        link = LandingSurvey.objects.create(landing=self.landing, survey=self.survey)
        LandingBlock.objects.create(landing=self.landing, kind='survey', landing_survey=link, data={})
        SurveyHeader.objects.filter(pk=self.survey.pk).update(status='archived')
        self.assertEqual(landings.page_blocks(self.landing), [])


class LandingPublicPageTest(LandingTestBase):
    def publish(self):
        self.login(self.editor)
        self.client.post(self.url('editor_landing_publish'), {'action': 'publish'})
        self.client.logout()

    def test_draft_is_private(self):
        """GIVEN a draft landing
        WHEN an anonymous visitor opens its address
        THEN the survey-unavailable 404 answers"""
        r = self.client.get('/p/riverside-park-plan/')
        self.assertEqual(r.status_code, 404)
        self.assertTemplateUsed(r, 'survey_unavailable.html')

    def test_member_previews_draft(self):
        """GIVEN a draft landing
        WHEN a member of the workspace opens the same URL
        THEN the page renders with the draft banner and noindex"""
        self.login(self.viewer)
        r = self.client.get('/p/riverside-park-plan/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Draft — only your workspace sees this.')
        self.assertContains(r, 'noindex')

    def test_published_page_renders_every_kind(self):
        """GIVEN a published landing with every kind of block
        WHEN anyone opens it
        THEN each block, the anchor menu and the open survey card render"""
        self.login(self.editor)
        self._every_kind()
        self.publish()
        r = self.client.get('/p/riverside-park-plan/')
        self.assertEqual(r.status_code, 200)
        for needle in ('About the park', 'Read the plan', 'player.vimeo.com/video/123456789', 'Q?',
                       'lp-phase', 'Take part', f'/surveys/{self.survey.uuid}/', 'href="#b-'):
            self.assertContains(r, needle)
        self.assertNotContains(r, 'noindex')

    def test_unlisted(self):
        """GIVEN a published unlisted landing
        WHEN it is requested and the sitemap is built
        THEN the page carries noindex and the sitemap has no entry"""
        Landing.objects.filter(pk=self.landing.pk).update(visibility='unlisted')
        self.publish()
        self.assertContains(self.client.get('/p/riverside-park-plan/'), '<meta name="robots" content="noindex">')
        self.assertNotContains(self.client.get('/sitemap.xml'), '/p/riverside-park-plan/')

    def test_public_in_sitemap(self):
        """GIVEN a published public landing
        WHEN the sitemap is built
        THEN it lists the landing"""
        self.publish()
        self.assertContains(self.client.get('/sitemap.xml'), '/p/riverside-park-plan/')

    @override_settings(POSTHOG_PROJECT_KEY='phc_test_key')
    def test_no_analytics(self):
        """GIVEN a PostHog key is configured
        WHEN a published landing renders
        THEN the response carries no PostHog snippet"""
        self.publish()
        r = self.client.get('/p/riverside-park-plan/')
        self.assertNotContains(r, 'phc_test_key')
        self.assertNotContains(r, 'posthog')

    def test_language_and_branding(self):
        """GIVEN a German landing of a Pro workspace
        WHEN it renders
        THEN html lang is de and the Made-with badge is absent"""
        Landing.objects.filter(pk=self.landing.pk).update(language='de')
        self.publish()
        r = self.client.get('/p/riverside-park-plan/')
        self.assertContains(r, '<html lang="de">')
        self.assertNotContains(r, 'utm_medium=landing')


class LandingProGateTest(LandingTestBase):
    def test_free_workspace_refused(self):
        """GIVEN a Free workspace whose owner's trial is used elsewhere
        WHEN an editor tries to create a landing
        THEN the response is 403 with the feature page and no landing exists"""
        self.sub.delete()
        trial_used_elsewhere(self.org)
        self.login(self.editor)
        r = self.client.post(reverse('editor_landing_create'), {'title': 'New'})
        self.assertEqual(r.status_code, 403)
        self.assertTemplateUsed(r, 'billing/feature_required.html')
        self.assertFalse(Landing.objects.filter(title='New').exists())

    def test_trial_allows_one_landing(self):
        """GIVEN a Free workspace that has never had a trial
        WHEN an editor creates two landings
        THEN the first starts the trial and is created; the second is refused"""
        self.sub.delete()
        self.login(self.editor)
        self.assertEqual(self.client.post(reverse('editor_landing_create'), {'title': 'First'}).status_code, 302)
        self.assertEqual(self.client.post(reverse('editor_landing_create'), {'title': 'Second'}).status_code, 403)

    def test_lapsed_keeps_page(self):
        """GIVEN a landing published under Pro whose subscription then ended
        WHEN the page is opened, a block saved and the landing unpublished
        THEN the page renders, the save is 403 and unpublish succeeds"""
        self.login(self.editor)
        self.client.post(self.url('editor_landing_publish'), {'action': 'publish'})
        self.sub.status = STATUS_FINISHED
        self.sub.current_period_end = timezone.now() - timedelta(days=1)
        self.sub.save()
        trial_used_elsewhere(self.org)
        self.client.logout()
        self.assertEqual(self.client.get('/p/riverside-park-plan/').status_code, 200)
        self.login(self.editor)
        self.assertEqual(self.add_block('text', body='<p>x</p>').status_code, 403)
        r = self.client.get(self.url('editor_landing'))
        self.assertContains(r, 'part of Pro')
        self.client.post(self.url('editor_landing_publish'), {'action': 'unpublish'})
        self.landing.refresh_from_db()
        self.assertFalse(self.landing.is_published)


@override_settings(CONTENT_SCREENING=True)
class LandingScreeningTest(LandingTestBase):
    def setUp(self):
        super().setUp()
        from survey.tests.helpers import _eager_notice
        patcher = _eager_notice()
        patcher.start()
        self.addCleanup(patcher.stop)

    @override_settings(CONTENT_SCREENING_HOLD_THRESHOLD=0)
    def test_lure_held(self):
        """GIVEN a threshold every text reaches
        WHEN a landing is published
        THEN a pending review names it, the moderator is mailed and visitors get 404"""
        from django.core import mail
        self.login(self.editor)
        self.client.post(self.url('editor_landing_publish'), {'action': 'publish'})
        review = ContentReview.objects.get(landing=self.landing)
        self.assertEqual(review.status, 'pending')
        self.assertIsNone(review.survey_id)
        self.assertTrue(any('Landing page held for review' in m.subject for m in mail.outbox))
        self.client.logout()
        self.assertEqual(self.client.get('/p/riverside-park-plan/').status_code, 404)
        self.assertNotContains(self.client.get('/sitemap.xml'), '/p/riverside-park-plan/')

    def test_live_edit_rescreens(self):
        """GIVEN a published landing
        WHEN a lure button is added
        THEN screening runs again (live_edit) and can hold it"""
        self.login(self.editor)
        self.client.post(self.url('editor_landing_publish'), {'action': 'publish'})
        with override_settings(CONTENT_SCREENING_HOLD_THRESHOLD=0):
            self.add_block('button', label='Verify your account', url='https://bit.ly/x')
        self.assertEqual(ContentReview.objects.get(landing=self.landing).trigger, 'live_edit')

    def test_report(self):
        """GIVEN a published landing
        WHEN a visitor reports it as phishing
        THEN a reported review names the landing and the page keeps serving"""
        self.login(self.editor)
        self.client.post(self.url('editor_landing_publish'), {'action': 'publish'})
        self.client.logout()
        r = self.client.post('/p/riverside-park-plan/report/', {'reason': 'phishing', 'message': 'fake'})
        self.assertEqual(r.status_code, 200)
        review = ContentReview.objects.get(landing=self.landing)
        self.assertEqual(review.status, 'reported')
        self.assertEqual(self.client.get('/p/riverside-park-plan/').status_code, 200)

    def test_review_names_one_subject(self):
        """GIVEN a review row
        WHEN it names both a survey and a landing, or neither
        THEN the database refuses it"""
        for kw in ({'survey': self.survey, 'landing': self.landing}, {}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                ContentReview.objects.create(**kw)

    def test_confirm_landing_review(self):
        """GIVEN a pending landing review
        WHEN staff confirm phishing
        THEN the creator is deactivated, their surveys closed and their landings unpublished"""
        Landing.objects.filter(pk=self.landing.pk).update(is_published=True)
        review = ContentReview.objects.create(landing=self.landing, status='pending')
        staff = User.objects.create_user('staff', 'st@example.test', 'pass', is_staff=True)
        confirm_phishing(review, staff)
        self.owner.refresh_from_db()
        self.landing.refresh_from_db()
        self.survey.refresh_from_db()
        self.assertFalse(self.owner.is_active)
        self.assertFalse(self.landing.is_published)
        self.assertEqual(self.survey.status, 'closed')

    def test_review_page_names_landing(self):
        """GIVEN a pending landing review
        WHEN staff open the review page
        THEN it names the landing and links to its public page"""
        from survey.content_screening import review_path
        review = ContentReview.objects.create(landing=self.landing, status='pending')
        staff = User.objects.create_user('staff', 'st@example.test', 'pass', is_staff=True)
        self.client.force_login(staff)
        r = self.client.get(review_path(review))
        self.assertContains(r, 'Riverside Park plan')
        self.assertContains(r, '/p/riverside-park-plan/')
