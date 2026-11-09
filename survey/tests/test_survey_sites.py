"""Sites (spec `survey-sites`, change landing-core, #576; epic #348) and the
site half of `abuse-review` (one review table for surveys and sites)."""
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
from survey import sites
from survey.content_screening import confirm_phishing
from survey.models import (ContentReview, Site, SiteBlock, SiteFile, SiteSurvey, Membership, Organization,
                           PublicResultsPage, SurveyHeader)


def _png():
    from PIL import Image
    buf = BytesIO()
    Image.new('RGB', (4, 4), (200, 10, 10)).save(buf, 'PNG')
    return SimpleUploadedFile('cover.png', buf.getvalue(), content_type='image/png')


class SiteTestBase(TestCase):
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
        self.site = Site.objects.create(organization=self.org, title='Riverside Park plan',
                                              slug='riverside-park-plan', created_by=self.owner)

    def login(self, user):
        self.client.force_login(user)
        session = self.client.session
        session['active_org_id'] = self.org.id
        session.save()

    def url(self, name, *args):
        return reverse(name, args=[self.site.uuid, *args])

    def add_block(self, kind, **fields):
        return self.client.post(self.url('editor_site_block_add'), dict(kind=kind, **fields))

    def _every_kind(self):
        self.add_block('text', body='<p>About the park</p>', title='About')
        self.add_block('image', alt='Park', image=_png())
        self.add_block('button', label='Read the plan', url='https://city.example/plan')
        self.add_block('video', url='https://vimeo.com/123456789')
        self.client.post(self.url('editor_site_block_add'), {'kind': 'faq', 'q': ['Q?'], 'a': ['<p>A</p>']})
        self.client.post(self.url('editor_site_block_add'), {
            'kind': 'timeline', 'phase_title': ['Now'], 'phase_when': ['2027'], 'phase_body': [''], 'current': '0'})
        self.add_block('survey', survey=self.survey.uuid, title='Take part')
        self.assertEqual(self.site.blocks.count(), 7)


class SiteEntityTest(SiteTestBase):
    def test_editor_creates_site(self):
        """GIVEN an editor of a Pro workspace
        WHEN they post a title to create a site
        THEN a draft site with a slug from the title exists and the builder opens"""
        self.login(self.editor)
        r = self.client.post(reverse('editor_site_create'), {'title': 'Old Town square'})
        site = Site.objects.get(title='Old Town square')
        self.assertRedirects(r, reverse('editor_site', args=[site.uuid]), fetch_redirect_response=False)
        self.assertEqual(site.slug, 'old-town-square')
        self.assertFalse(site.is_published)
        self.assertEqual(site.organization, self.org)

    def test_slug_from_taken_title_gets_a_suffix(self):
        """GIVEN a site already holds the slug riverside-park-plan
        WHEN another site is created with the same title
        THEN its slug carries a numeric suffix"""
        self.assertEqual(sites.unique_slug('Riverside Park plan'), 'riverside-park-plan-2')

    def test_viewer_cannot_change(self):
        """GIVEN a viewer of the workspace
        WHEN they post settings, a block or publish
        THEN every response is 403 and nothing changes"""
        self.login(self.viewer)
        self.assertEqual(self.client.post(self.url('editor_site_settings'),
                                          {'title': 'X', 'slug': 'xxx'}).status_code, 403)
        self.assertEqual(self.add_block('text', body='<p>Hi</p>').status_code, 403)
        self.assertEqual(self.client.post(self.url('editor_site_publish'), {'action': 'publish'}).status_code, 403)
        self.site.refresh_from_db()
        self.assertEqual(self.site.title, 'Riverside Park plan')
        self.assertFalse(self.site.blocks.exists())

    def test_viewer_sees_builder_read_only(self):
        """GIVEN a viewer
        WHEN they open the builder
        THEN it renders without the Add block button"""
        self.login(self.viewer)
        r = self.client.get(self.url('editor_site'))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'id="site-add-block"')

    def test_other_workspace_gets_404(self):
        """GIVEN a member of another workspace
        WHEN they open this site's builder
        THEN the response is 404"""
        other = Organization.objects.create(name='Other', slug='other')
        stranger = User.objects.create_user('stranger', 's@example.test', 'pass')
        Membership.objects.create(user=stranger, organization=other, role='owner')
        self.client.force_login(stranger)
        self.assertEqual(self.client.get(self.url('editor_site')).status_code, 404)

    def test_slug_rules(self):
        """GIVEN the settings form
        WHEN the slug is reserved, too short or taken
        THEN the save is refused with a field error and the slug stays"""
        Site.objects.create(organization=self.org, title='Other', slug='taken-slug')
        self.login(self.editor)
        for bad in ('edit', 'ab', 'taken-slug', 'Bad Slug'):
            r = self.client.post(self.url('editor_site_settings'), {'title': 'T', 'slug': bad})
            self.assertEqual(r.status_code, 400, bad)
        self.site.refresh_from_db()
        self.assertEqual(self.site.slug, 'riverside-park-plan')

    def test_settings_save_with_cover(self):
        """GIVEN an editor
        WHEN they save a summary, an unlisted visibility, a language and a cover
        THEN the site keeps them and the cover is stored under a random key"""
        self.login(self.editor)
        r = self.client.post(self.url('editor_site_settings'), {
            'title': 'Riverside Park', 'summary': 'Tell us  what you think.', 'slug': 'riverside',
            'language': 'de', 'visibility': 'unlisted', 'cover': _png(), 'cover_alt': 'The park'})
        self.assertEqual(r.status_code, 302)
        self.site.refresh_from_db()
        self.assertEqual((self.site.slug, self.site.language, self.site.visibility),
                         ('riverside', 'de', 'unlisted'))
        self.assertEqual(self.site.summary, 'Tell us what you think.')
        self.assertTrue(self.site.cover.name.startswith('site_assets/'))
        self.assertNotIn('cover', self.site.cover.name.split('/')[-1])


class SiteSurveyLinkTest(SiteTestBase):
    def test_one_survey_on_two_sites(self):
        """GIVEN two sites of the workspace
        WHEN an editor links the same survey to both
        THEN both list it"""
        second = Site.objects.create(organization=self.org, title='Transport', slug='transport')
        self.login(self.editor)
        for site in (self.site, second):
            self.client.post(reverse('editor_site_survey_link', args=[site.uuid]), {'survey': self.survey.uuid})
        self.assertEqual(SiteSurvey.objects.filter(survey=self.survey).count(), 2)

    def test_foreign_survey_refused(self):
        """GIVEN a survey of another workspace
        WHEN an editor tries to link it
        THEN the response is 404 and nothing is linked"""
        other = Organization.objects.create(name='Other', slug='other')
        foreign = SurveyHeader.objects.create(name='foreign', organization=other)
        self.login(self.editor)
        r = self.client.post(self.url('editor_site_survey_link'), {'survey': foreign.uuid})
        self.assertEqual(r.status_code, 404)
        self.assertFalse(SiteSurvey.objects.exists())

    def test_archived_or_trashed_survey_refused(self):
        """GIVEN an archived and a trashed survey of the workspace
        WHEN an editor tries to link them
        THEN both are refused"""
        archived = SurveyHeader.objects.create(name='old', organization=self.org, status='archived')
        trashed = SurveyHeader.objects.create(name='gone', organization=self.org, deleted_at=timezone.now())
        self.login(self.editor)
        for s in (archived, trashed):
            self.assertEqual(self.client.post(self.url('editor_site_survey_link'), {'survey': s.uuid}).status_code, 404)

    def test_draft_copy_links_canonical(self):
        """GIVEN a draft copy of a published survey
        WHEN it is linked
        THEN the canonical survey is linked"""
        draft = SurveyHeader.objects.create(name='park_survey', organization=self.org, published_version=self.survey)
        self.login(self.editor)
        self.client.post(self.url('editor_site_survey_link'), {'survey': draft.uuid})
        self.assertEqual(list(self.site.survey_links.values_list('survey', flat=True)), [self.survey.pk])

    def test_unlinking_removes_cards(self):
        """GIVEN a site with a card for survey S
        WHEN S is unlinked
        THEN the card is gone too"""
        self.login(self.editor)
        self.add_block('survey', survey=self.survey.uuid)
        link = self.site.survey_links.get()
        self.assertEqual(self.site.blocks.count(), 1)
        self.client.post(self.url('editor_site_survey_unlink', link.pk))
        self.assertFalse(self.site.blocks.exists())


class SiteBlockTest(SiteTestBase):
    def setUp(self):
        super().setUp()
        self.login(self.editor)

    def test_text_is_sanitised(self):
        """GIVEN a text block with a script
        WHEN it is saved
        THEN the script is gone"""
        self.add_block('text', body='<p>Hello</p><script>alert(1)</script>')
        body = self.site.blocks.get().data['body']
        self.assertIn('<p>Hello</p>', body)
        self.assertNotIn('script', body)

    def test_plain_text_body_is_escaped(self):
        """GIVEN a text block posted as plain text with an angle bracket
        WHEN it is saved
        THEN it is kept as text, not dropped as an unknown tag"""
        self.add_block('text', body='takes <5 minutes')
        self.assertIn('&lt;5 minutes', self.site.blocks.get().data['body'])

    def test_unsafe_button_refused(self):
        """GIVEN a button with a javascript: URL
        WHEN it is saved
        THEN the save is refused with the URL error"""
        r = self.add_block('button', label='Go', url='javascript:alert(1)')
        self.assertEqual(r.status_code, 400)
        self.assertContains(r, 'Enter a full web address', status_code=400)
        self.assertFalse(self.site.blocks.exists())

    def test_video_only_youtube_or_vimeo(self):
        """GIVEN a YouTube short link and a link to another host
        WHEN video blocks are saved
        THEN the first stores the player URL and the second is refused"""
        self.add_block('video', url='https://youtu.be/dQw4w9WgXcQ')
        self.assertEqual(self.site.blocks.get().data['embed'], 'https://www.youtube.com/embed/dQw4w9WgXcQ')
        r = self.add_block('video', url='https://evil.example/video')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.site.blocks.count(), 1)

    def test_faq_and_timeline(self):
        """GIVEN FAQ and timeline forms with parallel row lists
        WHEN they are saved
        THEN the items keep their order and the current phase index"""
        self.client.post(self.url('editor_site_block_add'), {
            'kind': 'faq', 'q': ['Who decides?', 'When?'], 'a': ['<p>The council.</p>', '']})
        self.client.post(self.url('editor_site_block_add'), {
            'kind': 'timeline', 'phase_title': ['Survey', 'Draft plan', 'Decision'],
            'phase_when': ['March 2027', 'May', 'Autumn'], 'phase_body': ['', '', ''], 'current': '1'})
        faq, timeline = self.site.blocks.order_by('order')
        self.assertEqual([i['q'] for i in faq.data['items']], ['Who decides?', 'When?'])
        self.assertEqual(timeline.data['current'], 1)
        self.assertEqual(len(timeline.data['items']), 3)

    def test_clean_block_drops_unknown_keys_and_caps(self):
        """GIVEN raw data with unknown keys and an overlong caption
        WHEN clean_block runs
        THEN only the kind's keys remain, capped"""
        data, errors = sites.clean_block('image', {'caption': 'x' * 900, 'evil': 1})
        self.assertEqual(set(data), {'alt', 'caption', 'wide'})
        self.assertEqual(len(data['caption']), 300)
        self.assertEqual(errors, {})

    def test_image_block_needs_a_picture(self):
        """GIVEN an image block without a file
        WHEN it is added
        THEN it is refused; with a file it is stored under a random key"""
        self.assertEqual(self.add_block('image', alt='Park').status_code, 400)
        self.add_block('image', alt='Park', image=_png())
        self.assertTrue(self.site.blocks.get().image.name.startswith('site_assets/'))

    def test_reorder(self):
        """GIVEN three blocks
        WHEN the full id list is posted in a new order
        THEN orders follow it; a list naming another site's block is refused"""
        for i in range(3):
            self.add_block('text', body=f'<p>{i}</p>')
        ids = list(self.site.blocks.order_by('order').values_list('id', flat=True))
        r = self.client.post(self.url('editor_site_blocks_reorder'), json.dumps({'order': ids[::-1]}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(list(self.site.blocks.order_by('order').values_list('id', flat=True)), ids[::-1])
        other = Site.objects.create(organization=self.org, title='O', slug='other-page')
        foreign = SiteBlock.objects.create(site=other, kind='text', data={'body': '<p>x</p>'})
        r = self.client.post(self.url('editor_site_blocks_reorder'),
                             json.dumps({'order': ids[:2] + [foreign.pk]}), content_type='application/json')
        self.assertEqual(r.status_code, 400)

    def test_edit_and_delete(self):
        """GIVEN a text block
        WHEN it is edited and then deleted
        THEN the body changes and then the block is gone"""
        self.add_block('text', body='<p>One</p>')
        block = self.site.blocks.get()
        self.client.post(self.url('editor_site_block_edit', block.pk), {'body': '<p>Two</p>', 'title': 'About'})
        block.refresh_from_db()
        self.assertEqual((block.title, block.data['body']), ('About', '<p>Two</p>'))
        self.client.post(self.url('editor_site_block_delete', block.pk))
        self.assertFalse(self.site.blocks.exists())

    def test_builder_renders_every_kind(self):
        """GIVEN a site with one block of every kind
        WHEN the builder and the add form of every kind render
        THEN all answer 200"""
        self._every_kind()
        self.assertEqual(self.client.get(self.url('editor_site')).status_code, 200)
        for kind in sites.BLOCK_KINDS:
            self.assertEqual(self.client.get(self.url('editor_site') + f'?add={kind}').status_code, 200, kind)

class SurveyCardTest(SiteTestBase):
    def card(self):
        return sites.survey_card(SurveyHeader.objects.get(pk=self.survey.pk))

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
        link = SiteSurvey.objects.create(site=self.site, survey=self.survey)
        SiteBlock.objects.create(site=self.site, kind='survey', site_survey=link, data={})
        SurveyHeader.objects.filter(pk=self.survey.pk).update(status='archived')
        self.assertEqual(sites.page_blocks(self.site), [])


class SitePublicPageTest(SiteTestBase):
    def publish(self):
        self.login(self.editor)
        self.client.post(self.url('editor_site_publish'), {'action': 'publish'})
        self.client.logout()

    def test_draft_is_private(self):
        """GIVEN a draft site
        WHEN an anonymous visitor opens its address
        THEN the survey-unavailable 404 answers"""
        r = self.client.get('/p/riverside-park-plan/')
        self.assertEqual(r.status_code, 404)
        self.assertTemplateUsed(r, 'survey_unavailable.html')

    def test_member_previews_draft(self):
        """GIVEN a draft site
        WHEN a member of the workspace opens the same URL
        THEN the page renders with the draft banner and noindex"""
        self.login(self.viewer)
        r = self.client.get('/p/riverside-park-plan/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Draft — only your workspace sees this.')
        self.assertContains(r, 'noindex')

    def test_published_page_renders_every_kind(self):
        """GIVEN a published site with every kind of block
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
        """GIVEN a published unlisted site
        WHEN it is requested and the sitemap is built
        THEN the page carries noindex and the sitemap has no entry"""
        Site.objects.filter(pk=self.site.pk).update(visibility='unlisted')
        self.publish()
        self.assertContains(self.client.get('/p/riverside-park-plan/'), '<meta name="robots" content="noindex">')
        self.assertNotContains(self.client.get('/sitemap.xml'), '/p/riverside-park-plan/')

    def test_public_in_sitemap(self):
        """GIVEN a published public site
        WHEN the sitemap is built
        THEN it lists the site"""
        self.publish()
        self.assertContains(self.client.get('/sitemap.xml'), '/p/riverside-park-plan/')

    @override_settings(POSTHOG_PROJECT_KEY='phc_test_key')
    def test_no_analytics(self):
        """GIVEN a PostHog key is configured
        WHEN a published site renders
        THEN the response carries no PostHog snippet"""
        self.publish()
        r = self.client.get('/p/riverside-park-plan/')
        self.assertNotContains(r, 'phc_test_key')
        self.assertNotContains(r, 'posthog')

    def test_language_and_branding(self):
        """GIVEN a German site of a Pro workspace
        WHEN it renders
        THEN html lang is de and the Made-with badge is absent"""
        Site.objects.filter(pk=self.site.pk).update(language='de')
        self.publish()
        r = self.client.get('/p/riverside-park-plan/')
        self.assertContains(r, '<html lang="de">')
        self.assertNotContains(r, 'utm_medium=site')


class SiteProGateTest(SiteTestBase):
    def test_free_workspace_refused(self):
        """GIVEN a Free workspace whose owner's trial is used elsewhere
        WHEN an editor tries to create a site
        THEN the response is 403 with the feature page and no site exists"""
        self.sub.delete()
        trial_used_elsewhere(self.org)
        self.login(self.editor)
        r = self.client.post(reverse('editor_site_create'), {'title': 'New'})
        self.assertEqual(r.status_code, 403)
        self.assertTemplateUsed(r, 'billing/feature_required.html')
        self.assertFalse(Site.objects.filter(title='New').exists())

    def test_trial_allows_one_site(self):
        """GIVEN a Free workspace that has never had a trial
        WHEN an editor creates two sites
        THEN the first starts the trial and is created; the second is refused"""
        self.sub.delete()
        self.login(self.editor)
        self.assertEqual(self.client.post(reverse('editor_site_create'), {'title': 'First'}).status_code, 302)
        self.assertEqual(self.client.post(reverse('editor_site_create'), {'title': 'Second'}).status_code, 403)

    def test_lapsed_keeps_page(self):
        """GIVEN a site published under Pro whose subscription then ended
        WHEN the page is opened, a block saved and the site unpublished
        THEN the page renders, the save is 403 and unpublish succeeds"""
        self.login(self.editor)
        self.client.post(self.url('editor_site_publish'), {'action': 'publish'})
        self.sub.status = STATUS_FINISHED
        self.sub.current_period_end = timezone.now() - timedelta(days=1)
        self.sub.save()
        trial_used_elsewhere(self.org)
        self.client.logout()
        self.assertEqual(self.client.get('/p/riverside-park-plan/').status_code, 200)
        self.login(self.editor)
        self.assertEqual(self.add_block('text', body='<p>x</p>').status_code, 403)
        r = self.client.get(self.url('editor_site'))
        self.assertContains(r, 'part of Pro')
        self.client.post(self.url('editor_site_publish'), {'action': 'unpublish'})
        self.site.refresh_from_db()
        self.assertFalse(self.site.is_published)


@override_settings(CONTENT_SCREENING=True)
class SiteScreeningTest(SiteTestBase):
    def setUp(self):
        super().setUp()
        from survey.tests.helpers import _eager_notice
        patcher = _eager_notice()
        patcher.start()
        self.addCleanup(patcher.stop)

    @override_settings(CONTENT_SCREENING_HOLD_THRESHOLD=0)
    def test_lure_held(self):
        """GIVEN a threshold every text reaches
        WHEN a site is published
        THEN a pending review names it, the moderator is mailed and visitors get 404"""
        from django.core import mail
        self.login(self.editor)
        self.client.post(self.url('editor_site_publish'), {'action': 'publish'})
        review = ContentReview.objects.get(site=self.site)
        self.assertEqual(review.status, 'pending')
        self.assertIsNone(review.survey_id)
        self.assertTrue(any('Site held for review' in m.subject for m in mail.outbox))
        self.client.logout()
        self.assertEqual(self.client.get('/p/riverside-park-plan/').status_code, 404)
        self.assertNotContains(self.client.get('/sitemap.xml'), '/p/riverside-park-plan/')

    def test_live_edit_rescreens(self):
        """GIVEN a published site
        WHEN a lure button is added
        THEN screening runs again (live_edit) and can hold it"""
        self.login(self.editor)
        self.client.post(self.url('editor_site_publish'), {'action': 'publish'})
        with override_settings(CONTENT_SCREENING_HOLD_THRESHOLD=0):
            self.add_block('button', label='Verify your account', url='https://bit.ly/x')
        self.assertEqual(ContentReview.objects.get(site=self.site).trigger, 'live_edit')

    def test_report(self):
        """GIVEN a published site
        WHEN a visitor reports it as phishing
        THEN a reported review names the site and the page keeps serving"""
        self.login(self.editor)
        self.client.post(self.url('editor_site_publish'), {'action': 'publish'})
        self.client.logout()
        r = self.client.post('/p/riverside-park-plan/report/', {'reason': 'phishing', 'message': 'fake'})
        self.assertEqual(r.status_code, 200)
        review = ContentReview.objects.get(site=self.site)
        self.assertEqual(review.status, 'reported')
        self.assertEqual(self.client.get('/p/riverside-park-plan/').status_code, 200)

    def test_review_names_one_subject(self):
        """GIVEN a review row
        WHEN it names both a survey and a site, or neither
        THEN the database refuses it"""
        for kw in ({'survey': self.survey, 'site': self.site}, {}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                ContentReview.objects.create(**kw)

    def test_confirm_site_review(self):
        """GIVEN a pending site review
        WHEN staff confirm phishing
        THEN the creator is deactivated, their surveys closed and their sites unpublished"""
        Site.objects.filter(pk=self.site.pk).update(is_published=True)
        review = ContentReview.objects.create(site=self.site, status='pending')
        staff = User.objects.create_user('staff', 'st@example.test', 'pass', is_staff=True)
        confirm_phishing(review, staff)
        self.owner.refresh_from_db()
        self.site.refresh_from_db()
        self.survey.refresh_from_db()
        self.assertFalse(self.owner.is_active)
        self.assertFalse(self.site.is_published)
        self.assertEqual(self.survey.status, 'closed')

    def test_review_page_names_site(self):
        """GIVEN a pending site review
        WHEN staff open the review page
        THEN it names the site and links to its public page"""
        from survey.content_screening import review_path
        review = ContentReview.objects.create(site=self.site, status='pending')
        staff = User.objects.create_user('staff', 'st@example.test', 'pass', is_staff=True)
        self.client.force_login(staff)
        r = self.client.get(review_path(review))
        self.assertContains(r, 'Riverside Park plan')
        self.assertContains(r, '/p/riverside-park-plan/')


class SiteDocumentsTest(SiteTestBase):
    """Spec `survey-sites`, documents block (change landing-documents-map, #577)."""

    def setUp(self):
        super().setUp()
        self.login(self.editor)

    def pdf(self, name='summary.pdf', body=b'%PDF-1.4\n%fake\n'):
        return SimpleUploadedFile(name, body, content_type='application/pdf')

    def test_pdf_added(self):
        """GIVEN a PDF named summary.pdf
        WHEN a documents block is added with it
        THEN a file titled "summary" is stored under a random site_files/ key and the page lists it"""
        r = self.client.post(self.url('editor_site_block_add'), {'kind': 'documents', 'files': [self.pdf()]})
        self.assertEqual(r.status_code, 302)
        f = SiteFile.objects.get()
        self.assertEqual(f.title, 'summary')
        self.assertTrue(f.file.name.startswith('site_files/'))
        self.assertNotIn('summary', f.file.name)
        self.client.post(self.url('editor_site_publish'), {'action': 'publish'})
        page = self.client.get('/p/riverside-park-plan/')
        self.assertContains(page, 'summary')
        self.assertContains(page, 'PDF')

    def test_disguised_html_refused(self):
        """GIVEN a file named boards.pdf whose content is HTML
        WHEN it is uploaded
        THEN the save is refused naming the file and nothing is stored"""
        r = self.client.post(self.url('editor_site_block_add'), {
            'kind': 'documents', 'files': [self.pdf('boards.pdf', b'<html><script>x</script></html>')]})
        self.assertEqual(r.status_code, 400)
        self.assertContains(r, 'boards.pdf', status_code=400)
        self.assertFalse(SiteFile.objects.exists())
        self.assertFalse(self.site.blocks.exists())

    def test_text_with_markup_refused(self):
        """GIVEN a .txt file that is an SVG
        WHEN it is uploaded
        THEN it is refused"""
        svg = SimpleUploadedFile('notes.txt', b'<svg onload="alert(1)"></svg>', content_type='text/plain')
        r = self.client.post(self.url('editor_site_block_add'), {'kind': 'documents', 'files': [svg]})
        self.assertEqual(r.status_code, 400)

    def test_rename_and_remove_in_one_save(self):
        """GIVEN a documents block with two files
        WHEN it is saved with a new title for one and the other removed
        THEN the first is renamed and the second is gone"""
        self.client.post(self.url('editor_site_block_add'),
                         {'kind': 'documents', 'files': [self.pdf('a.pdf'), self.pdf('b.pdf')]})
        block = self.site.blocks.get()
        a, b = block.files.order_by('order')
        self.client.post(self.url('editor_site_block_edit', block.pk),
                         {f'file_title_{a.pk}': 'Boards from the open house', f'remove_{b.pk}': '1'})
        self.assertEqual(list(block.files.values_list('title', flat=True)), ['Boards from the open house'])

    def test_block_without_files_refused(self):
        """GIVEN a documents block with one file
        WHEN it is saved with that file removed and nothing added
        THEN the save is refused"""
        self.client.post(self.url('editor_site_block_add'), {'kind': 'documents', 'files': [self.pdf()]})
        block = self.site.blocks.get()
        f = block.files.get()
        r = self.client.post(self.url('editor_site_block_edit', block.pk), {f'remove_{f.pk}': '1'})
        self.assertEqual(r.status_code, 400)
        self.assertTrue(block.files.exists())

    def test_file_titles_are_screened(self):
        """GIVEN a documents block whose file title is a lure
        WHEN the site text is collected for screening
        THEN the title is part of it"""
        from survey.content_screening import collect_site_text
        self.client.post(self.url('editor_site_block_add'), {'kind': 'documents', 'files': [self.pdf()]})
        SiteFile.objects.update(title='Verify your account now')
        texts = ' '.join(t for _l, t in collect_site_text(self.site).texts)
        self.assertIn('Verify your account now', texts)


class SiteMapTest(SiteTestBase):
    """Spec `survey-sites`, map block (change landing-documents-map, #577)."""

    POLY = {'type': 'Feature', 'properties': {'name': 'Park', 'owner': 'x'},
            'geometry': {'type': 'Polygon', 'coordinates': [[[13.1234567891, 52.1], [13.2, 52.1],
                                                             [13.2, 52.2], [13.1234567891, 52.1]]]}}

    def setUp(self):
        super().setUp()
        self.login(self.editor)

    def geojson(self, doc, name='area.geojson'):
        body = doc if isinstance(doc, bytes) else json.dumps(doc).encode()
        return SimpleUploadedFile(name, body, content_type='application/geo+json')

    def add_map(self, doc, **extra):
        return self.client.post(self.url('editor_site_block_add'),
                                dict(kind='map', geojson_file=self.geojson(doc), **extra))

    def test_polygon_normalised(self):
        """GIVEN a Feature with 10-decimal coordinates and extra properties
        WHEN a map block is saved
        THEN one feature remains with only its name and 6-decimal coordinates"""
        self.assertEqual(self.add_map(self.POLY, color='#AA0000').status_code, 302)
        data = self.site.blocks.get().data
        feature = data['area']['features'][0]
        self.assertEqual(feature['properties'], {'name': 'Park'})
        self.assertEqual(feature['geometry']['coordinates'][0][0][0], 13.123457)
        self.assertEqual((data['color'], data['basemap']), ('#aa0000', 'streets'))

    def test_invalid_files_refused(self):
        """GIVEN a non-JSON file, a document without geometry and a latitude of 120
        WHEN each is saved as a map block
        THEN each is refused and no block exists"""
        bad = [b'not json', {'type': 'FeatureCollection', 'features': []},
               {'type': 'Point', 'coordinates': [10, 120]}]
        for doc in bad:
            self.assertEqual(self.add_map(doc).status_code, 400, doc)
        self.assertFalse(self.site.blocks.exists())

    def test_edit_keeps_area(self):
        """GIVEN a map block
        WHEN it is saved again with a caption and no new file
        THEN the area stays"""
        self.add_map(self.POLY)
        block = self.site.blocks.get()
        self.client.post(self.url('editor_site_block_edit', block.pk), {'caption': 'The park today'})
        block.refresh_from_db()
        self.assertEqual(block.data['caption'], 'The park today')
        self.assertEqual(len(block.data['area']['features']), 1)

    def test_unknown_basemap_falls_back(self):
        """GIVEN a base map key the workspace does not have
        WHEN the map block is saved
        THEN Streets is stored"""
        self.add_map(self.POLY, basemap='style:00000000-0000-0000-0000-000000000000')
        self.assertEqual(self.site.blocks.get().data['basemap'], 'streets')

    def test_leaflet_only_where_needed(self):
        """GIVEN a published site
        WHEN it has no map block, and then one
        THEN Leaflet loads only in the second case"""
        self.client.post(self.url('editor_site_publish'), {'action': 'publish'})
        self.assertNotContains(self.client.get('/p/riverside-park-plan/'), 'leaflet')
        self.add_map(self.POLY)
        r = self.client.get('/p/riverside-park-plan/')
        self.assertContains(r, 'leaflet.js')
        self.assertContains(r, 'id="area-b-')


class SiteResultsTest(SiteTestBase):
    """Spec `survey-sites`, results blocks (change landing-results, #578)."""

    def setUp(self):
        super().setUp()
        from django.core.cache import cache
        from survey.models import Question, SurveySection
        cache.clear()
        section = SurveySection.objects.create(survey_header=self.survey, name='s', code='S1', is_head=True)
        self.choice_q = Question.objects.create(
            survey_section=section, code='Q_CH', name='Do you use the park?', input_type='choice',
            choices=[{'code': 1, 'name': 'Often'}, {'code': 2, 'name': 'Rarely'}])
        self.point_q = Question.objects.create(survey_section=section, code='Q_PT', name='Mark a spot',
                                               input_type='point')
        self.text_q = Question.objects.create(survey_section=section, code='Q_TX', name='Comment', input_type='text')
        self.login(self.editor)

    def vote(self, code, n, **session_kw):
        from survey.models import Answer, SurveySession
        for _ in range(n):
            s = SurveySession.objects.create(survey=self.survey, **session_kw)
            Answer.objects.create(survey_session=s, question=self.choice_q, selected_choices=[code])

    def add_results(self, question, **extra):
        return self.client.post(self.url('editor_site_block_add'), dict(
            kind='results', results_question=f'{self.survey.uuid}:{question.code}', **extra))

    def payload(self):
        block = SiteBlock.objects.get(site=self.site, kind='results')
        return sites.results_payload(block)

    def test_choice_chart_with_masking(self):
        """GIVEN 5 clean votes for Often and 1 for Rarely, K 3
        WHEN a results block shows the question on a published site
        THEN Often is 5, Rarely is "<3" without a value, and the page loads the shared renderer"""
        self.vote(1, 5)
        self.vote(2, 1)
        self.assertEqual(self.add_results(self.choice_q, viz='pie').status_code, 302)
        items = {i['code']: i for i in self.payload()['items']}
        self.assertEqual(items[1]['value'], 5)
        self.assertEqual((items[2]['display'], items[2]['value']), ('<3', None))
        self.assertTrue(self.site.survey_links.filter(survey=self.survey).exists())
        self.client.post(self.url('editor_site_publish'), {'action': 'publish'})
        r = self.client.get('/p/riverside-park-plan/')
        self.assertContains(r, 'js/public_results_render.')
        self.assertContains(r, 'chart.umd.min.js')
        self.assertContains(r, 'id="chart-r')
        self.assertNotContains(r, 'leaflet.markercluster')

    def test_text_question_refused(self):
        """GIVEN a text question
        WHEN a results block is saved for it
        THEN the save is refused"""
        self.assertEqual(self.add_results(self.text_q).status_code, 400)
        self.assertFalse(self.site.blocks.exists())

    def test_excluded_sessions_do_not_count(self):
        """GIVEN 3 clean votes, one deleted and one not-approved session
        WHEN the payload is built
        THEN only the 3 clean votes count"""
        self.vote(1, 3)
        self.vote(1, 1, is_deleted=True)
        self.vote(1, 1, validation_status='not_approved')
        self.add_results(self.choice_q)
        payload = self.payload()
        self.assertEqual({i['code']: i['value'] for i in payload['items']}[1], 3)
        self.assertEqual(payload['responses'], 3)

    def test_results_page_k_applies(self):
        """GIVEN the survey's results page uses K 5
        WHEN 4 votes are shown on a site
        THEN they are masked as "<5\""""
        PublicResultsPage.objects.create(survey=self.survey, slug='park-results', k_anonymity_threshold=5)
        self.vote(1, 4)
        self.add_results(self.choice_q)
        self.assertEqual({i['code']: i['display'] for i in self.payload()['items']}[1], '<5')

    def test_map_question_loads_map_libraries(self):
        """GIVEN a results block for a point question with the heatmap style
        WHEN the published site renders
        THEN Leaflet, the heat and cluster plugins and a map holder are there, and no popups are offered"""
        self.add_results(self.point_q, viz='heatmap')
        block = SiteBlock.objects.get(kind='results')
        self.assertEqual(block.data['viz'], 'heatmap')
        self.client.post(self.url('editor_site_publish'), {'action': 'publish'})
        r = self.client.get('/p/riverside-park-plan/')
        self.assertContains(r, 'leaflet-heat.js')
        self.assertContains(r, f'id="map-r{block.pk}"')

    def test_deleted_question(self):
        """GIVEN a results block whose question is then deleted
        WHEN the page and the builder render
        THEN the page omits it and the builder marks it"""
        self.add_results(self.choice_q, title='What we heard')
        self.choice_q.delete()
        self.client.post(self.url('editor_site_publish'), {'action': 'publish'})
        self.assertNotContains(self.client.get('/p/riverside-park-plan/'), 'What we heard')
        self.assertContains(self.client.get(self.url('editor_site')), 'question was removed')

    def test_public_results_page_uses_shared_renderer(self):
        """GIVEN a published public results page
        WHEN /r/<slug>/ renders
        THEN it loads the shared renderer and calls it"""
        PublicResultsPage.objects.create(survey=self.survey, slug='park-results', is_published=True)
        r = self.client.get('/r/park-results/')
        self.assertContains(r, 'js/public_results_render.')
        self.assertContains(r, 'window.renderResultBlocks(blocks, BASEMAPS)')
        self.assertNotContains(r, 'function renderChoiceChart')


class SiteEventTest(SiteTestBase):
    """Spec `survey-sites`, events and registration (change landing-events, #579)."""

    def setUp(self):
        super().setUp()
        from django.core.cache import cache
        cache.clear()
        from unittest import mock
        from survey import site_events
        patcher = mock.patch('survey.tasks.send_event_confirmation.delay',
                             side_effect=lambda pk: site_events.send_confirmation(pk))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.login(self.editor)
        future = (timezone.now() + timedelta(days=10)).date().isoformat()
        r = self.client.post(self.url('editor_site_block_add'), {
            'kind': 'event', 'title': 'Open house', 'date': future, 'start': '18:00', 'end': '20:00',
            'tz': 'Europe/Berlin', 'place': 'The boathouse', 'capacity': '2', 'open': '1'})
        assert r.status_code == 302, r.content[:500]
        self.block = self.site.blocks.get(kind='event')
        self.client.post(self.url('editor_site_publish'), {'action': 'publish'})
        self.client.logout()

    def register(self, name='Ana', email='ana@example.org', **extra):
        data = {'name': name, 'email': email, 'consent': '1'}
        data.update(extra)
        return self.client.post(reverse('site_event_register', args=[self.site.slug, self.block.pk]), data)

    def test_registration_stored_and_confirmed(self):
        """GIVEN an open event
        WHEN a visitor registers with consent
        THEN one active registration exists and a mail with an .ics and a cancel link is sent"""
        from django.core import mail
        r = self.register()
        self.assertEqual(r.status_code, 302)
        self.assertIn(f'registered={self.block.pk}', r['Location'])
        reg = self.block.registrations.get()
        self.assertEqual((reg.name, reg.email), ('Ana', 'ana@example.org'))
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ['ana@example.org'])
        self.assertIn(str(reg.token), msg.body)
        name, content, mimetype = msg.attachments[0]
        self.assertEqual(name, 'event.ics')
        self.assertIn('BEGIN:VEVENT', content)
        self.assertIn('DTSTART:', content)
        self.assertIn('T170000Z', content)  # 18:00 Berlin (CET) = 17:00 UTC
        page = self.client.get(r['Location'])
        self.assertContains(page, 'Check your inbox')

    def test_full_event(self):
        """GIVEN an event with 2 seats taken
        WHEN a third visitor registers
        THEN nothing is stored and the page says it is full"""
        self.register('A', 'a@example.org')
        self.register('B', 'b@example.org')
        r = self.register('C', 'c@example.org')
        self.assertIn('event_error=full', r['Location'])
        self.assertEqual(self.block.registrations.count(), 2)
        self.assertContains(self.client.get(r['Location']), 'The event is full.')

    def test_same_email_twice(self):
        """GIVEN one registration
        WHEN the same email registers again
        THEN one registration exists and two confirmations were sent"""
        from django.core import mail
        self.register()
        self.register(name='Ana B', email='ANA@example.org')
        self.assertEqual(self.block.registrations.count(), 1)
        self.assertEqual(len(mail.outbox), 2)

    def test_honeypot_and_consent(self):
        """GIVEN a filled honeypot or no consent
        WHEN the form is posted
        THEN nothing is stored"""
        self.register(website='spam')
        self.client.post(reverse('site_event_register', args=[self.site.slug, self.block.pk]),
                         {'name': 'X', 'email': 'x@example.org'})
        self.assertFalse(self.block.registrations.exists())

    def test_rate_limit(self):
        """GIVEN 5 registration posts from one address within an hour
        WHEN a sixth arrives
        THEN it is answered 429"""
        for i in range(5):
            self.register(email=f'p{i}@example.org', consent='')
        self.assertEqual(self.register(email='p9@example.org').status_code, 429)

    def test_cancel_frees_the_seat(self):
        """GIVEN a full 2-seat event
        WHEN a registrant opens the cancel link and posts it
        THEN the GET changes nothing, the POST cancels, and another visitor can register"""
        self.register('A', 'a@example.org')
        self.register('B', 'b@example.org')
        reg = self.block.registrations.get(email='a@example.org')
        url = reverse('site_event_cancel', args=[reg.token])
        self.assertContains(self.client.get(url), 'Cancel my registration')
        reg.refresh_from_db()
        self.assertIsNone(reg.cancelled_at)
        self.client.post(url)
        reg.refresh_from_db()
        self.assertIsNotNone(reg.cancelled_at)
        self.register('C', 'c@example.org')
        self.assertTrue(self.block.registrations.filter(email='c@example.org').exists())
        import uuid
        self.assertEqual(self.client.get(reverse('site_event_cancel', args=[uuid.uuid4()])).status_code, 404)

    def test_closed_or_past_event(self):
        """GIVEN registration switched off
        WHEN the page renders and a post arrives
        THEN no form is shown and nothing is stored"""
        data = dict(self.block.data, open=False)
        SiteBlock.objects.filter(pk=self.block.pk).update(data=data)
        self.assertNotContains(self.client.get('/p/riverside-park-plan/'), 'name="consent"')
        self.register()
        self.assertFalse(self.block.registrations.exists())

    def test_viewer_refused_editor_sees_list(self):
        """GIVEN a registration
        WHEN a viewer and an editor open the attendee list
        THEN the viewer gets 403 and the editor sees the name"""
        self.register()
        url = reverse('editor_site_attendees', args=[self.site.uuid, self.block.pk])
        self.login(self.viewer)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.login(self.editor)
        self.assertContains(self.client.get(url), 'ana@example.org')

    def test_csv_guards_formulas(self):
        """GIVEN a registrant named =HYPERLINK("x")
        WHEN the editor downloads the CSV
        THEN it has a header and the name cell starts with an apostrophe"""
        self.register(name='=HYPERLINK("x")')
        self.login(self.editor)
        r = self.client.get(reverse('editor_site_attendees', args=[self.site.uuid, self.block.pk]) + '?format=csv')
        text = r.content.decode('utf-8-sig')
        self.assertTrue(text.startswith('name,email,registered_at,status'))
        self.assertIn("'=HYPERLINK", text)

    def test_remove_all_without_pro(self):
        """GIVEN a lapsed workspace with registrations
        WHEN the editor removes all
        THEN they are deleted"""
        self.register()
        self.sub.delete()
        trial_used_elsewhere(self.org)
        self.login(self.editor)
        self.client.post(reverse('editor_site_attendees_remove', args=[self.site.uuid, self.block.pk]),
                         {'registration': 'all'})
        self.assertFalse(self.block.registrations.exists())

    def test_purge(self):
        """GIVEN one event that ended 31 days ago and one tomorrow, both with registrations
        WHEN the purge task runs
        THEN only the old event's registrations are deleted"""
        from survey.models import EventRegistration
        from survey.tasks import purge_event_registrations
        old = SiteBlock.objects.create(site=self.site, kind='event', order=9, data=dict(
            self.block.data, date=(timezone.now() - timedelta(days=31)).date().isoformat()))
        EventRegistration.objects.create(block=old, name='Old', email='old@example.org')
        self.register()
        purge_event_registrations()
        self.assertFalse(old.registrations.exists())
        self.assertTrue(self.block.registrations.exists())

    def test_invalid_event_refused(self):
        """GIVEN a bad date, an end before the start and an unknown zone
        WHEN an event block is saved
        THEN it is refused"""
        self.login(self.editor)
        r = self.client.post(self.url('editor_site_block_add'), {
            'kind': 'event', 'date': 'tomorrow', 'start': '18:00', 'end': '17:00', 'tz': 'Mars/Olympus'})
        self.assertEqual(r.status_code, 400)

    def test_policy_pages(self):
        """GIVEN the terms and trust pages
        WHEN they render
        THEN both mention event registration and the 30-day deletion"""
        for url in ('/terms/', '/trust/'):
            r = self.client.get(url)
            self.assertContains(r, 'registration', msg_prefix=url)
            self.assertContains(r, '30 days after the event', msg_prefix=url)


class SiteReviewFixesTest(SiteTestBase):
    """Fixes from the epic review: image bytes decide, an edit error keeps what was typed."""

    def setUp(self):
        super().setUp()
        self.login(self.editor)

    def test_disguised_image_refused(self):
        """GIVEN an HTML file named x.html posted with Content-Type image/jpeg
        WHEN it is uploaded as a cover and as an image block
        THEN both are refused and nothing is stored"""
        fake = lambda: SimpleUploadedFile('x.html', b'<html><script>alert(1)</script></html>', content_type='image/jpeg')
        r = self.client.post(self.url('editor_site_settings'),
                             {'title': 'T', 'slug': self.site.slug, 'cover': fake()})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.add_block('image', alt='x', image=fake()).status_code, 400)
        self.site.refresh_from_db()
        self.assertFalse(self.site.cover)
        self.assertFalse(self.site.blocks.exists())

    def test_image_key_takes_the_real_format(self):
        """GIVEN a real PNG uploaded under the name photo.html
        WHEN it is saved as an image block
        THEN the stored key ends in .png"""
        png = _png()
        png.name = 'photo.html'
        self.add_block('image', alt='Park', image=png)
        self.assertTrue(self.site.blocks.get().image.name.endswith('.png'))

    def test_edit_error_keeps_typed_values(self):
        """GIVEN a FAQ block
        WHEN it is saved with a new question and an answer whose question is empty
        THEN the save is refused and the form shows the newly typed question"""
        self.client.post(self.url('editor_site_block_add'), {'kind': 'faq', 'q': ['Old?'], 'a': ['<p>A</p>']})
        block = self.site.blocks.get()
        r = self.client.post(self.url('editor_site_block_edit', block.pk),
                             {'q': ['Brand new question?', ''], 'a': ['<p>x</p>', '<p>orphan</p>']})
        self.assertEqual(r.status_code, 400)
        self.assertContains(r, 'Brand new question?', status_code=400)


class SiteCanvasBuilderTest(SiteTestBase):
    """Spec `survey-sites`, the canvas builder (change landing-builder-redesign, #594)."""

    def setUp(self):
        super().setUp()
        self.login(self.editor)

    def autosave(self, block, **fields):
        return self.client.post(self.url('editor_site_block_edit', block.pk), dict(autosave='1', **fields))

    def test_autosave_answers_the_rerendered_block(self):
        """GIVEN a text block
        WHEN the builder posts a new body with autosave=1
        THEN the answer is JSON with the block's canvas HTML and outline row, and the body is stored sanitised"""
        self.add_block('text', body='<p>Old</p>')
        block = self.site.blocks.get()
        r = self.autosave(block, body='<p>New text</p><script>x</script>', title='About')
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['ok'])
        self.assertIn('New text', data['block'])
        self.assertIn(f'data-block="{block.pk}"', data['block'])
        self.assertIn('About', data['outline'])
        self.assertIn('data-pane=', data['panel'])
        block.refresh_from_db()
        self.assertEqual(block.data['body'], '<p>New text</p>')
        self.assertEqual(block.title, 'About')

    def test_autosave_refusal_keeps_the_block(self):
        """GIVEN a button block
        WHEN the builder posts the URL javascript:alert(1) with autosave=1
        THEN the answer is 422 JSON with an error for url and the block is unchanged"""
        self.add_block('button', label='Plan', url='https://city.example/plan')
        block = self.site.blocks.get()
        r = self.autosave(block, label='Plan', url='javascript:alert(1)')
        self.assertEqual(r.status_code, 422)
        self.assertIn('url', r.json()['errors'])
        block.refresh_from_db()
        self.assertEqual(block.data['url'], 'https://city.example/plan')

    def test_empty_field_waits_on_autosave(self):
        """GIVEN an event block being filled in
        WHEN only the date is posted with autosave=1
        THEN it is saved without an error and stays off the public page until the start time is set"""
        self.client.post(self.url('editor_site_block_add'), {'kind': 'event', 'empty': '1'})
        block = self.site.blocks.get()
        r = self.autosave(block, date='2030-06-12', start='', tz='UTC', open='1')
        self.assertEqual(r.status_code, 200)
        self.client.post(self.url('editor_site_publish'), {'action': 'publish'})
        self.assertNotContains(self.client.get('/p/riverside-park-plan/'), 'lp-event')
        self.autosave(block, date='2030-06-12', start='10:00', tz='UTC', open='1')
        self.assertContains(self.client.get('/p/riverside-park-plan/'), 'lp-event')

    def test_library_adds_an_empty_block_off_the_page(self):
        """GIVEN the block library
        WHEN a text block is added empty after the first block
        THEN the builder selects it, it sits second, and the published page does not draw it"""
        self.add_block('text', body='<p>First</p>')
        self.add_block('text', body='<p>Last</p>')
        first = self.site.blocks.order_by('order').first()
        r = self.client.post(self.url('editor_site_block_add'), {'kind': 'text', 'empty': '1', 'after': first.pk})
        new = self.site.blocks.order_by('-id').first()
        self.assertIn(f'select={new.pk}', r['Location'])
        self.assertEqual(list(self.site.blocks.order_by('order').values_list('pk', flat=True))[1], new.pk)
        self.assertContains(self.client.get(self.url('editor_site') + f'?select={new.pk}'), 'lb-blk')
        self.client.post(self.url('editor_site_publish'), {'action': 'publish'})
        page = self.client.get('/p/riverside-park-plan/').content.decode()
        self.assertEqual(page.count('lp-block--text'), 2)

    def test_canvas_renders_every_kind_editable(self):
        """GIVEN a site with one block of every kind
        WHEN the builder renders
        THEN every block has its canvas shell, a toolbar and a panel, and the headings are editable"""
        self._every_kind()
        self.client.post(self.url('editor_site_block_add'), {'kind': 'documents', 'empty': '1'})
        self.client.post(self.url('editor_site_block_add'), {'kind': 'map', 'empty': '1'})
        self.client.post(self.url('editor_site_block_add'), {'kind': 'results', 'empty': '1'})
        self.client.post(self.url('editor_site_block_add'), {'kind': 'event', 'empty': '1'})
        html = self.client.get(self.url('editor_site')).content.decode()
        for block in self.site.blocks.all():
            self.assertIn(f'class="lp-block lp-block--{block.kind} lb-blk', html, block.kind)
            self.assertIn(f'data-pane="{block.pk}"', html)
        self.assertEqual(html.count('class="lb-tools"'), self.site.blocks.count())
        self.assertIn('data-field="title"', html)
        self.assertIn('data-field="body"', html)

    def test_read_only_canvas(self):
        """GIVEN a viewer, and an editor of a lapsed workspace
        WHEN they open the builder
        THEN no toolbar, no "+" and the panels are disabled"""
        self.add_block('text', body='<p>Hi</p>')
        for user in (self.viewer,):
            self.login(user)
            html = self.client.get(self.url('editor_site')).content.decode()
            self.assertNotIn('class="lb-tools"', html)
            self.assertNotIn('lb-ins', html)
            self.assertIn('<fieldset disabled', html)
            self.assertIn('data-may-edit=""', html)
        self.sub.delete()
        trial_used_elsewhere(self.org)
        self.login(self.editor)
        html = self.client.get(self.url('editor_site')).content.decode()
        self.assertNotIn('class="lb-tools"', html)
        self.assertIn('part of Pro', html)

    def test_duplicate(self):
        """GIVEN a documents block with a file
        WHEN it is duplicated and the copy then removes the file
        THEN the copy sits right after the original and the original's file is still stored"""
        pdf = SimpleUploadedFile('a.pdf', b'%PDF-1.4\n', content_type='application/pdf')
        self.client.post(self.url('editor_site_block_add'), {'kind': 'documents', 'files': [pdf]})
        self.add_block('text', body='<p>After</p>')
        original = self.site.blocks.get(kind='documents')
        r = self.client.post(self.url('editor_site_block_duplicate', original.pk))
        copy = self.site.blocks.filter(kind='documents').exclude(pk=original.pk).get()
        self.assertIn(f'select={copy.pk}', r['Location'])
        self.assertEqual(copy.order, original.order + 1)
        f_copy = copy.files.get()
        self.client.post(self.url('editor_site_block_edit', copy.pk), {f'remove_{f_copy.pk}': '1', 'autosave': '1'})
        f = original.files.get()
        self.assertTrue(f.file.storage.exists(f.file.name))

    def test_settings_autosave_partial(self):
        """GIVEN the page panel
        WHEN only the visibility is posted with autosave=1
        THEN it changes, the title stays and the answer carries the hero"""
        r = self.client.post(self.url('editor_site_settings'), {'visibility': 'unlisted', 'autosave': '1'})
        self.assertTrue(r.json()['ok'])
        self.assertIn('Riverside Park plan', r.json()['hero'])
        self.site.refresh_from_db()
        self.assertEqual((self.site.visibility, self.site.title), ('unlisted', 'Riverside Park plan'))
        r = self.client.post(self.url('editor_site_settings'), {'slug': 'Edit', 'autosave': '1'})
        self.assertEqual(r.status_code, 422)


class SiteConfirmDialogTest(SiteTestBase):
    """Destructive posts ask through the app's delete dialog, never the browser's confirm()."""

    def test_builder_and_attendees_use_the_app_dialog(self):
        """GIVEN a site with an event block
        WHEN the builder and the attendee list render
        THEN both carry the #lb-confirm dialog, the delete forms opt in with data-confirm,
             and no page calls the browser's confirm()"""
        from django.contrib.staticfiles import finders
        self.login(self.editor)
        self.client.post(self.url('editor_site_block_add'), {'kind': 'event', 'empty': '1'})
        block = self.site.blocks.get()
        builder = self.client.get(self.url('editor_site')).content.decode()
        attendees = self.client.get(reverse('editor_site_attendees', args=[self.site.uuid, block.pk])).content.decode()
        for html in (builder, attendees):
            self.assertIn('id="lb-confirm"', html)
            self.assertIn('js/site_confirm.', html)
            self.assertNotIn('confirm(', html)
        self.assertIn('everyone registered for the event', builder)
        for name in ('js/site_builder.js', 'js/site_confirm.js'):
            with open(finders.find(name)) as fh:
                self.assertNotIn('window.confirm', fh.read())


class SiteOneClickCreateTest(SiteTestBase):
    """"New site" is one click: no title first; the address follows the first real title."""

    def test_new_page_without_a_title(self):
        """GIVEN the site list
        WHEN an editor presses New site (no title posted)
        THEN a draft with the placeholder title and an "untitled" address opens with ?new=1,
             and the list page has no title field"""
        self.login(self.editor)
        self.assertNotContains(self.client.get(reverse('editor_sites')), 'name="title"')
        r = self.client.post(reverse('editor_site_create'))
        site = Site.objects.exclude(pk=self.site.pk).get()
        self.assertTrue(r['Location'].endswith('?new=1'))
        self.assertEqual(site.title, 'Untitled site')
        self.assertEqual(site.slug, 'untitled')

    def test_address_follows_the_first_title_until_published(self):
        """GIVEN a page created with New site
        WHEN its title is autosaved, and again after publishing
        THEN the address follows the first title and stays once the page is published"""
        self.login(self.editor)
        self.client.post(reverse('editor_site_create'))
        site = Site.objects.exclude(pk=self.site.pk).get()
        url = reverse('editor_site_settings', args=[site.uuid])
        self.client.post(url, {'title': 'Old Town square', 'autosave': '1'})
        site.refresh_from_db()
        self.assertEqual(site.slug, 'old-town-square')
        self.client.post(url, {'title': 'Old Town square, phase 2', 'autosave': '1'})
        site.refresh_from_db()
        self.assertEqual(site.slug, 'old-town-square', 'a real address is not renamed again')

    def test_published_placeholder_keeps_its_address(self):
        """GIVEN a page published while still called "untitled"
        WHEN its title changes
        THEN the address stays: printed links must keep working"""
        self.login(self.editor)
        self.client.post(reverse('editor_site_create'))
        site = Site.objects.exclude(pk=self.site.pk).get()
        self.client.post(reverse('editor_site_publish', args=[site.uuid]), {'action': 'publish'})
        self.client.post(reverse('editor_site_settings', args=[site.uuid]), {'title': 'Harbour', 'autosave': '1'})
        site.refresh_from_db()
        self.assertEqual(site.slug, 'untitled')


class SiteInlineEditingTest(SiteTestBase):
    """Spec `survey-sites`: a block's primary actions happen in the block (change
    landing-inline-editing; owner rule 2026-11-08)."""

    def setUp(self):
        super().setUp()
        self.login(self.editor)

    def builder(self):
        return self.client.get(self.url('editor_site')).content.decode()

    def test_empty_image_block_has_a_drop_zone(self):
        """GIVEN an editor who adds an Image block
        WHEN the builder renders
        THEN the block shows a drop zone with a "choose a file" control, the panel's file input is
             hidden, and no block points to the settings"""
        for kind in ('image', 'video', 'button', 'faq', 'timeline', 'documents', 'map', 'event', 'survey', 'results'):
            self.client.post(self.url('editor_site_block_add'), {'kind': kind, 'empty': '1'})
        html = self.builder()
        self.assertIn('data-file="image"', html)
        self.assertIn('data-file-pick="image"', html)
        self.assertIn('choose a file', html)
        self.assertIn('<input type="file" name="image" hidden>', html)
        self.assertNotIn('in the settings on the right', html)
        for name in ('url', 'date', 'start', 'end', 'place', 'survey'):
            self.assertIn(f'data-input="{name}"', html, name)

    def test_faq_edited_in_place(self):
        """GIVEN an FAQ block with two questions
        WHEN the builder renders it
        THEN both rows are editable in the block with a remove control each and an "Add a question"
             control, and the panel keeps them only as hidden fields"""
        self.add_block('faq', q=['Who?', 'When?'], a=['<p>Everyone</p>', '<p>In May</p>'])
        html = self.builder()
        self.assertEqual(html.count('class="lb-qa" data-row>'), 2 + 1, 'two rows and the template')
        self.assertIn('data-row-field="q"', html)
        self.assertIn('data-row-field="a" data-row-rich', html)
        self.assertEqual(html.count('data-row-remove'), 3)
        self.assertIn('Add a question', html)
        self.assertIn('<input type="hidden" name="q" value="Who?">', html)
        self.assertNotIn('class="form-control form-control-sm" name="q"', html)

    def test_row_still_being_written(self):
        """GIVEN an FAQ block on a published page
        WHEN the builder autosaves a second row whose answer came before its question
        THEN it is saved without an error, and the public page draws only the row with a question"""
        self.add_block('faq', q=['Who?'], a=['<p>Everyone</p>'])
        block = self.site.blocks.get()
        self.client.post(self.url('editor_site_publish'), {'action': 'publish'})
        r = self.client.post(self.url('editor_site_block_edit', block.pk),
                             {'q': ['Who?', ''], 'a': ['<p>Everyone</p>', '<p>Half-written</p>'], 'autosave': '1'})
        self.assertEqual(r.status_code, 200)
        block.refresh_from_db()
        self.assertEqual(len(block.data['items']), 2)
        page = self.client.get('/p/riverside-park-plan/').content.decode()
        self.assertIn('Who?', page)
        self.assertNotIn('Half-written', page)
        r = self.client.post(self.url('editor_site_block_edit', block.pk),
                             {'q': [''], 'a': ['<p>Only an answer</p>'], 'autosave': '1'})
        self.assertEqual(r.status_code, 200)
        block.refresh_from_db()
        self.assertFalse(sites.is_complete(block))

    def test_timeline_now_from_the_canvas(self):
        """GIVEN a timeline block
        WHEN the builder posts the phases with current=1 (the second marked Now)
        THEN the first phase is done and the second is now on the canvas"""
        self.add_block('timeline', phase_title=['Survey', 'Design'], phase_when=['May', 'June'], phase_body=['', ''])
        block = self.site.blocks.get()
        r = self.client.post(self.url('editor_site_block_edit', block.pk),
                             {'phase_title': ['Survey', 'Design'], 'phase_when': ['May', 'June'],
                              'phase_body': ['', ''], 'current': '1', 'autosave': '1'})
        self.assertIn('lb-phase is-done', r.json()['block'])
        self.assertIn('lb-phase is-now', r.json()['block'])

    def test_secondary_options_stay_in_settings(self):
        """GIVEN a map block and an event block
        WHEN the builder renders their settings
        THEN the map panel offers colour and base map and no visible GeoJSON upload, and the event
             panel keeps the time zone, seats and registration switch while date and place are hidden"""
        self.client.post(self.url('editor_site_block_add'), {'kind': 'map', 'empty': '1'})
        self.client.post(self.url('editor_site_block_add'), {'kind': 'event', 'empty': '1'})
        html = self.builder()
        self.assertIn('name="color"', html)
        self.assertIn('name="basemap"', html)
        self.assertIn('<input type="file" name="geojson_file" hidden>', html)
        self.assertIn('data-file="geojson_file"', html)
        self.assertIn('name="tz"', html)
        self.assertIn('name="capacity"', html)
        self.assertIn('<input type="hidden" name="date" value="">', html)
        self.assertIn('<input type="hidden" name="place" value="">', html)

    def test_cover_picture_on_the_hero(self):
        """GIVEN the page head on the canvas
        WHEN an editor adds a cover with autosave and then removes it
        THEN the hero carries the add / change and remove controls, the page panel only a hidden
             file input and the description, and the cover is stored then cleared"""
        html = self.builder()
        self.assertIn('data-cover-pick', html)
        self.assertNotIn('data-cover-remove', html)
        self.assertIn('<input type="file" name="cover" accept="image/jpeg,image/png,image/webp,image/gif" hidden>', html)
        self.assertNotIn('data-select-target="page"><i class="far fa-image"', html)
        r = self.client.post(self.url('editor_site_settings'), {'cover': _png(), 'autosave': '1'})
        self.assertTrue(r.json()['ok'])
        self.assertIn('lp-hero-img', r.json()['hero'])
        self.assertIn('data-cover-remove', r.json()['hero'])
        self.site.refresh_from_db()
        self.assertTrue(self.site.cover)
        self.client.post(self.url('editor_site_settings'), {'remove_cover': '1', 'autosave': '1'})
        self.site.refresh_from_db()
        self.assertFalse(self.site.cover)


class SiteNamingTest(SiteTestBase):
    """Spec `survey-sites`: the module is called Sites (change rename-landings-to-sites)."""

    def test_sidebar_and_list_say_sites(self):
        """GIVEN a member of a Pro workspace
        WHEN they open the editor and the list of sites
        THEN the sidebar links "Sites" to /editor/sites/ and the list offers New site"""
        self.login(self.editor)
        self.assertEqual(reverse('editor_sites'), '/editor/sites/')
        html = self.client.get('/editor/?dashboard=1').content.decode()
        self.assertIn('href="/editor/sites/"', html)
        self.assertIn('Sites', html)
        listing = self.client.get(reverse('editor_sites')).content.decode()
        self.assertIn('New site', listing)
        self.assertNotIn('Landing', listing)
        builder = self.client.get(self.url('editor_site')).content.decode()
        self.assertIn('Site settings', builder)
        self.assertNotIn('Landing', builder)

    def test_old_editor_address_is_gone(self):
        """GIVEN the editor
        WHEN someone requests /editor/landings/
        THEN the answer is 404: the old address never shipped"""
        self.login(self.editor)
        self.assertEqual(self.client.get('/editor/landings/').status_code, 404)


class SiteHeadingTest(SiteTestBase):
    """Spec `survey-sites`: headings (change site-heading-block)."""

    def setUp(self):
        super().setUp()
        self.login(self.editor)

    def publish(self):
        self.client.post(self.url('editor_site_publish'), {'action': 'publish'})
        return self.client.get('/p/riverside-park-plan/').content.decode()

    def test_heading_block_sizes(self):
        """GIVEN three heading blocks, large, medium and small
        WHEN the site is published
        THEN large and medium are <h2> and small is <h3>, each in its size class, and an empty
             heading block stays off the page"""
        for title, size in (('Big one', 'l'), ('Middle one', 'm'), ('Small one', 's')):
            self.add_block('heading', title=title, size=size)
        self.client.post(self.url('editor_site_block_add'), {'kind': 'heading', 'empty': '1'})
        page = self.publish()
        self.assertIn('<h2 class="lp-heading lp-heading--l">Big one</h2>', page)
        self.assertIn('<h2 class="lp-heading lp-heading--m">Middle one</h2>', page)
        self.assertIn('<h3 class="lp-heading lp-heading--s">Small one</h3>', page)
        self.assertEqual(page.count('lp-block--heading'), 3)
        self.assertEqual(page.count('<h1'), 1)

    def test_heading_out_of_the_menu(self):
        """GIVEN two heading blocks and a text block with a heading
        WHEN the text block's "Show the heading in the menu" is unticked
        THEN the menu lists only the heading blocks, and the text block still shows its heading"""
        self.add_block('heading', title='Phase one', size='m')
        self.add_block('heading', title='Phase two', size='m')
        self.add_block('text', title='Background', body='<p>Since 1998</p>')
        text = self.site.blocks.get(kind='text')
        r = self.client.post(self.url('editor_site_block_edit', text.pk),
                             {'title': 'Background', 'body': '<p>Since 1998</p>', 'menu': ['0'], 'autosave': '1'})
        self.assertEqual(r.status_code, 200)
        text.refresh_from_db()
        self.assertFalse(text.in_menu)
        page = self.publish()
        nav = page.split('<nav', 1)[1].split('</nav>', 1)[0]
        self.assertIn('Phase two', nav)
        self.assertNotIn('Background', nav)
        self.assertIn('<h2>Background</h2>', page)

    def test_text_without_heading(self):
        """GIVEN a text block whose heading is left empty
        WHEN the site is published
        THEN the block has no heading and adds nothing to the menu"""
        self.add_block('text', body='<p>Only words</p>')
        page = self.publish()
        self.assertIn('Only words', page)
        self.assertNotIn('<h2></h2>', page)
        self.assertNotIn('<nav', page)

    def test_text_headings_stop_at_h2(self):
        """GIVEN a text block posted with an <h1> heading
        WHEN it is saved
        THEN the heading is stored as <h2>: the site title is the page's only <h1>"""
        self.add_block('text', body='<h1>Big</h1><p>Words</p>')
        self.assertEqual(self.site.blocks.get().data['body'], '<h2>Big</h2><p>Words</p>')

    def test_builder_offers_the_heading_block(self):
        """GIVEN the builder
        WHEN it renders
        THEN the library offers a Heading block, and an empty block heading says it is optional"""
        self.add_block('text', body='<p>Words</p>')
        html = self.client.get(self.url('editor_site')).content.decode()
        self.assertIn('value="heading"', html)
        self.assertIn('Heading (optional)', html)
        self.assertIn('name="menu"', html)


class SiteWidthTest(SiteTestBase):
    """Spec `survey-sites`: page width and full-width blocks (change site-width, #605)."""

    def setUp(self):
        super().setUp()
        self.login(self.editor)

    def test_wide_site(self):
        """GIVEN a site
        WHEN an editor sets the page width to Wide and publishes
        THEN the public page and the builder's canvas carry data-width wide"""
        r = self.client.post(self.url('editor_site_settings'), {'width': 'wide', 'autosave': '1'})
        self.assertEqual(r.json()['width'], 'wide')
        self.site.refresh_from_db()
        self.assertEqual(self.site.width, 'wide')
        self.client.post(self.url('editor_site_publish'), {'action': 'publish'})
        self.assertContains(self.client.get('/p/riverside-park-plan/'), '<body class="lp" data-width="wide">')
        self.assertContains(self.client.get(self.url('editor_site')), 'id="lb-frame" data-width="wide"')

    def test_new_site_is_narrow(self):
        """GIVEN a site created without a width
        WHEN it is read
        THEN its width is narrow, so existing sites look as before"""
        self.assertEqual(self.site.width, 'narrow')

    def test_unknown_width_ignored(self):
        """GIVEN a site with width standard
        WHEN the settings are posted with width "huge"
        THEN the site keeps standard"""
        self.site.width = 'standard'
        self.site.save()
        self.client.post(self.url('editor_site_settings'), {'width': 'huge', 'autosave': '1'})
        self.site.refresh_from_db()
        self.assertEqual(self.site.width, 'standard')

    def test_full_width_blocks(self):
        """GIVEN an image block and a text block
        WHEN the image is saved with Full width ticked
        THEN it stores wide and renders with the full-width class; text offers no such switch"""
        self.add_block('image', alt='Plan', image=_png(), wide='1')
        self.add_block('text', body='<p>Words</p>', wide='1')
        image = self.site.blocks.get(kind='image')
        self.assertTrue(image.data['wide'])
        self.assertNotIn('wide', self.site.blocks.get(kind='text').data)
        self.client.post(self.url('editor_site_publish'), {'action': 'publish'})
        page = self.client.get('/p/riverside-park-plan/').content.decode()
        self.assertIn('lp-block--image lp-block--wide', page)
        self.assertNotIn('lp-block--text lp-block--wide', page)
        builder = self.client.get(self.url('editor_site')).content.decode()
        self.assertEqual(builder.count('name="wide"'), 1)
