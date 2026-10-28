"""Tests for the `public-stories` capability (openspec/specs/public-stories/spec.md).

Moved from survey/tests.py by #273; classes are unchanged.
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
import json
from survey.models import SurveyHeader, Story, StoryImage
import tempfile
from io import StringIO
from django.core.management import call_command
from django.db.utils import IntegrityError
import shutil
from survey.tests.helpers import _make_org


class StoryModelTest(TestCase):
    """Tests for the Story model."""

    def setUp(self):
        self.org = _make_org()

    def test_create_story(self):
        """
        GIVEN valid story data
        WHEN a Story is created
        THEN it should be persisted and queryable
        """
        story = Story.objects.create(
            title="Test Story",
            slug="test-story",
            body="<p>Body</p>",
            story_type="article",
            is_published=True,
        )
        self.assertEqual(Story.objects.get(slug="test-story").title, "Test Story")

    def test_slug_uniqueness(self):
        """
        GIVEN an existing Story with a slug
        WHEN creating another Story with the same slug
        THEN the system should raise an IntegrityError
        """
        from django.db import IntegrityError
        Story.objects.create(title="A", slug="dup", story_type="article")
        with self.assertRaises(IntegrityError):
            Story.objects.create(title="B", slug="dup", story_type="article")

    def test_nullable_survey_fk(self):
        """
        GIVEN a Story without a survey FK
        WHEN created
        THEN it should be valid with survey as NULL
        """
        story = Story.objects.create(title="No Survey", slug="no-survey", story_type="map")
        self.assertIsNone(story.survey)

    def test_story_with_survey_fk(self):
        """
        GIVEN a Story linked to a SurveyHeader
        WHEN created
        THEN the story should reference that survey
        """
        survey = SurveyHeader.objects.create(name="linked_survey", organization=self.org)
        story = Story.objects.create(
            title="Linked", slug="linked", story_type="results", survey=survey,
        )
        self.assertEqual(story.survey, survey)


class StoryDetailViewTest(TestCase):
    """Tests for the story detail view."""

    def setUp(self):
        self.client = Client()
        self.org = _make_org()

    def test_published_story_returns_200(self):
        """
        GIVEN a published story
        WHEN navigating to /stories/<slug>/
        THEN the system returns 200
        """
        from django.utils import timezone
        Story.objects.create(
            title="Published", slug="published", story_type="article",
            is_published=True, published_date=timezone.now(),
        )
        response = self.client.get('/stories/published/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'story_detail.html')

    def test_unpublished_story_returns_404(self):
        """
        GIVEN an unpublished story
        WHEN navigating to /stories/<slug>/
        THEN the system returns 404
        """
        Story.objects.create(title="Draft", slug="draft-story", story_type="article", is_published=False)
        response = self.client.get('/stories/draft-story/')
        self.assertEqual(response.status_code, 404)

    def test_nonexistent_story_returns_404(self):
        """
        GIVEN no story with a given slug
        WHEN navigating to /stories/<slug>/
        THEN the system returns 404
        """
        response = self.client.get('/stories/does-not-exist/')
        self.assertEqual(response.status_code, 404)

    def test_story_with_survey_shows_link(self):
        """
        GIVEN a published story linked to a survey
        WHEN viewing the story detail
        THEN the page includes the survey name in the response
        """
        from django.utils import timezone
        survey = SurveyHeader.objects.create(name="linked_surv", organization=self.org)
        Story.objects.create(
            title="With Survey", slug="with-survey", story_type="results",
            is_published=True, published_date=timezone.now(), survey=survey,
        )
        response = self.client.get('/stories/with-survey/')
        self.assertContains(response, "linked_surv")

    def test_credit_links_when_urls_set(self):
        """
        GIVEN a published story whose credit and credit note carry URLs
        WHEN viewing the story detail
        THEN the credit and the note render as links to those URLs
        """
        from django.utils import timezone
        Story.objects.create(
            title="Credited", slug="credited", story_type="case-study",
            is_published=True, published_date=timezone.now(),
            credit="GRIA", credit_url="https://griaonline.org/",
            credit_note="survey by Unknown Studio", credit_note_url="https://unknownstudio.la/",
        )
        response = self.client.get('/stories/credited/')
        self.assertContains(response, '<a href="https://griaonline.org/" rel="noopener">GRIA</a>', html=False)
        self.assertContains(response, '<a href="https://unknownstudio.la/" rel="noopener">survey by Unknown Studio</a>', html=False)

    def test_credit_plain_when_no_urls(self):
        """
        GIVEN a published story with a credit but no URLs
        WHEN viewing the story detail
        THEN the credit renders as text, not as a link
        """
        from django.utils import timezone
        Story.objects.create(
            title="Plain", slug="plain-credit", story_type="case-study",
            is_published=True, published_date=timezone.now(), credit="Town Council",
        )
        response = self.client.get('/stories/plain-credit/')
        self.assertContains(response, "Town Council")
        self.assertNotContains(response, 'rel="noopener">Town Council')


class StoryShowcaseTest(TestCase):
    """Change customer-stories-showcase: the story page, the landing carousel and body images."""

    def setUp(self):
        from django.utils import timezone
        self.client = Client()
        self.story = Story.objects.create(
            title="Olney counts", slug="olney-counts", story_type="case-study",
            is_published=True, published_date=timezone.now(),
            place="Olney, Illinois", sector="Municipality",
            summary="Home of the White Squirrels.", credit="City of Olney",
            credit_note="administered by the City Clerk",
            facts=[{"value": "1977", "label": "first count", "chip": "Since 1977"}],
            body='<p>Route map:</p><img src="{img:routes}"><img src="{img:missing}">',
        )

    def _png(self, name="routes.png"):
        from django.core.files.uploadedfile import SimpleUploadedFile
        # A 1x1 PNG; ImageField validates the header on assignment.
        data = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00'
                b'\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00'
                b'\x00IEND\xaeB`\x82')
        return SimpleUploadedFile(name, data, content_type="image/png")

    def test_detail_renders_showcase_fields_and_resolves_image_tokens(self):
        """
        GIVEN a published story with place, summary, credit, a fact and a body that references
              one stored image and one unknown key
        WHEN its page is requested
        THEN the eyebrow, lead, credit and fact render, the known token becomes the stored
             file's URL and the unknown token becomes an empty src instead of a 500
        """
        img = StoryImage.objects.create(story=self.story, key="routes", image=self._png())
        response = self.client.get('/stories/olney-counts/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Olney, Illinois · Municipality")
        self.assertContains(response, "Home of the White Squirrels.")
        self.assertContains(response, "City of Olney")
        self.assertContains(response, "administered by the City Clerk")
        self.assertContains(response, "<b>1977</b>first count", html=False)
        self.assertContains(response, f'<img src="{img.image.url}">', html=False)
        self.assertContains(response, '<img src="">', html=False)
        self.assertNotContains(response, "{img:")

    def test_landing_carousel_shows_published_and_omits_draft(self):
        """
        GIVEN one published and one draft story
        WHEN the landing page is rendered
        THEN the "From the field" carousel holds the published story's card with its chip and
             credit, and the draft appears nowhere
        """
        Story.objects.create(title="Secret", slug="secret", story_type="article", is_published=False)
        response = self.client.get('/')
        self.assertContains(response, 'class="stories-carousel"')
        self.assertContains(response, 'href="/stories/olney-counts/"')
        self.assertContains(response, "Since 1977")
        self.assertContains(response, "City of Olney")
        self.assertNotContains(response, "Secret")
        self.assertNotContains(response, "/stories/secret/")

    def test_landing_omits_carousel_without_published_stories(self):
        """
        GIVEN no published story
        WHEN the landing page is rendered
        THEN the carousel section is absent, not empty
        """
        Story.objects.update(is_published=False)
        response = self.client.get('/')
        self.assertNotContains(response, 'class="stories-carousel"')

    def test_detail_ships_the_picture_lightbox(self):
        """
        GIVEN a published story, with or without pictures
        WHEN its page is requested
        THEN it carries the lightbox dialog (close, previous, next, caption) and the script that
             drives it, and the script is served by the static pipeline
        """
        response = self.client.get('/stories/olney-counts/')
        self.assertContains(response, 'id="storyLightbox"')
        self.assertContains(response, 'role="dialog"')
        self.assertContains(response, 'story-lightbox__close')
        self.assertContains(response, 'data-dir="-1"')
        self.assertContains(response, 'data-dir="1"')
        self.assertContains(response, 'id="storyLightboxCaption"')
        self.assertContains(response, 'js/story_lightbox')
        from django.contrib.staticfiles import finders
        self.assertIsNotNone(finders.find('js/story_lightbox.js'))

    def test_stories_index_uses_the_same_card(self):
        """
        GIVEN a published story
        WHEN /stories/ is rendered
        THEN its card carries the place, summary and credit like the landing card
        """
        response = self.client.get('/stories/')
        self.assertContains(response, 'href="/stories/olney-counts/"')
        self.assertContains(response, "Olney, Illinois")
        self.assertContains(response, "Home of the White Squirrels.")


class SeedStoryTest(TestCase):
    """`seed_story`: a customer story installed from survey/story_data/<slug>/."""

    SLUG = 'olney-white-squirrel-count'

    def _seed(self, *args):
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command('seed_story', self.SLUG, *args, stdout=out)
        return out.getvalue()

    def test_fresh_install_with_publish_publishes_the_story_with_its_pictures(self):
        """
        GIVEN a database without the Olney story
        WHEN seed_story runs with --publish
        THEN a published case study exists with the showcase fields, cover, card image, credit
             logo and every body image named in story.json, and its page renders every picture
        """
        out = self._seed('--publish')
        story = Story.objects.get(slug=self.SLUG)
        self.assertTrue(story.is_published)
        self.assertEqual(story.story_type, 'case-study')
        self.assertEqual(story.place, 'Olney, Illinois')
        self.assertEqual(story.credit, 'City of Olney, Illinois')
        self.assertEqual(len(story.facts), 4)
        self.assertTrue(story.cover_image and story.card_image and story.credit_logo)
        self.assertEqual(story.images.count(), 9)
        self.assertIn('installed (published)', out)
        response = Client().get(f'/stories/{self.SLUG}/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '{img:')
        self.assertNotContains(response, 'src=""')
        self.assertContains(response, 'City Clerk Kelsie Sterchi administers the count')

    def test_rerun_updates_in_place_and_keeps_the_date(self):
        """
        GIVEN the story already installed and then edited in the admin
        WHEN seed_story runs again
        THEN the same row (id, published_date) carries the repo's text again and the image set
             is unchanged in size
        """
        self._seed('--publish')
        story = Story.objects.get(slug=self.SLUG)
        first_id, first_date = story.id, story.published_date
        Story.objects.filter(pk=first_id).update(title='Edited by hand', body='')
        out = self._seed()
        story.refresh_from_db()
        self.assertEqual((story.id, story.published_date), (first_id, first_date))
        self.assertEqual(story.title, "Olney's white squirrel count, from paper maps to mobile devices")
        self.assertIn('{img:route-zones}', story.body)
        self.assertEqual(story.images.count(), 9)
        self.assertEqual(Story.objects.filter(slug=self.SLUG).count(), 1)
        self.assertIn('refreshed', out)
        self.assertTrue(story.is_published, 'a re-run without flags keeps a published story published')

    def test_draft_leaves_the_story_unpublished(self):
        """
        GIVEN nothing installed
        WHEN seed_story runs with --draft
        THEN the row exists, is unpublished, and the landing page does not show it
        """
        self._seed('--draft')
        story = Story.objects.get(slug=self.SLUG)
        self.assertFalse(story.is_published)
        self.assertEqual(Client().get(f'/stories/{self.SLUG}/').status_code, 404)
        self.assertNotContains(Client().get('/'), 'class="stories-carousel"')

    def test_unknown_slug_fails_and_changes_nothing(self):
        """
        GIVEN a slug with no data directory
        WHEN seed_story runs
        THEN it raises CommandError and creates no row
        """
        from django.core.management import call_command
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command('seed_story', 'no-such-story')
        self.assertFalse(Story.objects.exists())

    def test_sitemap_lists_the_seeded_story(self):
        """
        GIVEN the story installed and published
        WHEN sitemap.xml is requested
        THEN it lists the story URL with the published date
        """
        self._seed('--publish')
        body = Client().get('/sitemap.xml').content.decode()
        self.assertIn(f'/stories/{self.SLUG}/</loc><lastmod>2026-10-01</lastmod>', body)


class StoriesIndexViewTest(TestCase):
    """The public stories hub at /stories/: listing, empty state, SEO metadata."""

    import re as _re
    _LD_RE = _re.compile(r'<script type="application/ld\+json">(.*?)</script>', _re.S)

    def _ld(self, html):
        return [json.loads(b) for b in self._LD_RE.findall(html)]

    def _story(self, title, slug, published=True):
        from django.utils import timezone
        return Story.objects.create(
            title=title, slug=slug, story_type="results", body="<p>Body text about the project.</p>",
            is_published=published, published_date=timezone.now() if published else None,
        )

    def test_index_lists_published_not_draft(self):
        """
        GIVEN a published and a draft story
        WHEN /stories/ is requested
        THEN it returns 200, lists the published story with a detail link, and hides the draft
        """
        self._story("Riverside Engagement", "riverside")
        self._story("Secret Draft", "secret-draft", published=False)
        resp = Client().get("/stories/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Riverside Engagement")
        self.assertContains(resp, 'href="/stories/riverside/"')
        self.assertNotContains(resp, "Secret Draft")

    def test_empty_state_returns_200(self):
        """
        GIVEN no published stories
        WHEN /stories/ is requested
        THEN it returns 200 with an empty-state message (not a 404)
        """
        resp = Client().get("/stories/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "No stories published yet")

    def test_index_structured_data(self):
        """
        GIVEN published stories
        WHEN /stories/ is requested
        THEN it emits a valid BreadcrumbList (Home > Stories) and a CollectionPage
             whose ItemList has one entry per published story
        """
        self._story("Story A", "story-a")
        self._story("Story B", "story-b")
        blocks = self._ld(Client().get("/stories/").content.decode())
        bc = next(b for b in blocks if b.get("@type") == "BreadcrumbList")
        self.assertEqual([i["name"] for i in bc["itemListElement"]], ["Home", "Stories"])
        coll = next(b for b in blocks if b.get("@type") == "CollectionPage")
        self.assertEqual(len(coll["mainEntity"]["itemListElement"]), 2)

    def test_detail_seo_metadata(self):
        """
        GIVEN a published story
        WHEN its detail page is requested
        THEN it has a self-canonical, a non-empty meta description, and a
             3-item Home > Stories > <title> breadcrumb
        """
        self._story("Coastal Paths", "coastal-paths")
        resp = Client().get("/stories/coastal-paths/")
        html = resp.content.decode()
        self.assertIn('<link rel="canonical" href="https://mapsurvey.org/stories/coastal-paths/">', html)
        self.assertRegex(html, r'<meta name="description" content="[^"]+">')
        bc = next(b for b in self._ld(html) if b.get("@type") == "BreadcrumbList")
        self.assertEqual([i["name"] for i in bc["itemListElement"]], ["Home", "Stories", "Coastal Paths"])

    def test_sitemap_includes_hub_and_published_excludes_draft(self):
        """
        GIVEN a published and a draft story
        WHEN sitemap.xml is requested
        THEN it lists /stories/ and the published story URL but not the draft's
        """
        self._story("Published Story", "pub-story")
        self._story("Draft Story", "draft-story", published=False)
        body = Client().get("/sitemap.xml").content.decode()
        self.assertIn("/stories/</loc>", body)
        self.assertIn("/stories/pub-story/</loc>", body)
        self.assertNotIn("/stories/draft-story/", body)

    def test_landing_footer_links_to_stories(self):
        """
        GIVEN the shared landing footer
        WHEN a landing page is rendered
        THEN the footer links to the stories hub
        """
        resp = Client().get("/for-planners/")
        self.assertContains(resp, 'href="/stories/"')


class StoryDataDirectoriesTest(TestCase):
    """Every directory under survey/story_data/ is a story `seed_story` can install."""

    def test_every_story_directory_installs_and_renders_all_its_pictures(self):
        """
        GIVEN the story directories checked into the repo
        WHEN each one is seeded as a draft and its page is opened by a staff user
        THEN the row exists with a title, cover and credit, no {img:key} token is left unresolved
             (every key in story.json names a file that was uploaded) and the page renders 200
        """
        from django.core.management import call_command
        from survey.management.commands.seed_story import DATA_ROOT
        from survey.stories import IMAGE_TOKEN, render_body
        slugs = sorted(p.name for p in DATA_ROOT.iterdir() if (p / 'story.json').is_file())
        self.assertGreaterEqual(len(slugs), 1)
        for slug in slugs:
            with self.subTest(slug=slug):
                call_command('seed_story', slug, '--draft', stdout=StringIO())
                story = Story.objects.get(slug=slug)
                self.assertTrue(story.title and story.cover_image and story.credit, slug)
                self.assertFalse(story.is_published)
                keys = set(IMAGE_TOKEN.findall(story.body))
                owned = {img.key for img in story.images.all() if img.image}
                self.assertEqual(keys - owned, set(), f'{slug}: body references pictures story.json does not list')
                self.assertNotIn('src=""', render_body(story), slug)
                story.is_published = True
                story.save(update_fields=['is_published'])
                self.assertEqual(self.client.get(f'/stories/{slug}/').status_code, 200)


class StoryLessonsLearnedTest(TestCase):
    """Change story-lessons-learned: the callout marks a story, and its card shows a badge."""

    def setUp(self):
        from django.utils import timezone
        self.with_lessons = Story.objects.create(
            title="Dog bins", slug="dog-bins", story_type="case-study", is_published=True,
            published_date=timezone.now(),
            body='<p>Intro</p><aside class="sd-lessons" aria-label="Lessons learned"><h3>Lessons learned</h3></aside>',
        )
        self.without = Story.objects.create(
            title="Squirrels", slug="squirrels", story_type="case-study", is_published=True,
            published_date=timezone.now(), body='<p>No lessons here.</p>',
        )

    def test_has_lessons_reads_the_body(self):
        """GIVEN one story with the callout and one without
        WHEN has_lessons is read
        THEN it is True only for the story with the callout"""
        self.assertTrue(self.with_lessons.has_lessons)
        self.assertFalse(self.without.has_lessons)

    def test_card_badge_only_on_stories_with_lessons(self):
        """GIVEN two published stories, one with the callout
        WHEN the stories index renders
        THEN exactly one card carries the Lessons learned badge"""
        from django.urls import reverse
        response = self.client.get(reverse('stories_index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'story-card__lessons', count=1)


class StoryDraftPublishingTest(TestCase):
    """Change story-draft-publishing: drafts on production, published from the admin."""

    SLUG = 'olney-white-squirrel-count'

    def _seed(self, *args):
        from io import StringIO
        from django.core.management import call_command
        call_command('seed_story', self.SLUG, *args, stdout=StringIO())
        return Story.objects.get(slug=self.SLUG)

    def test_new_story_is_installed_as_a_draft(self):
        """GIVEN an empty database
        WHEN seed_story runs without flags
        THEN the story is unpublished, 404 for visitors, and absent from /stories/ and the sitemap"""
        story = self._seed()
        self.assertFalse(story.is_published)
        self.assertEqual(Client().get(f'/stories/{self.SLUG}/').status_code, 404)
        self.assertNotContains(Client().get('/stories/'), self.SLUG)
        self.assertNotContains(Client().get('/sitemap.xml'), self.SLUG)

    def test_rerun_keeps_a_draft_a_draft(self):
        """GIVEN a draft story
        WHEN seed_story runs again without flags
        THEN it is still a draft"""
        self._seed()
        self.assertFalse(self._seed().is_published)

    def test_staff_preview_has_banner_and_noindex(self):
        """GIVEN a draft story and a staff user
        WHEN the staff user opens its URL
        THEN the page renders with the draft banner and a noindex robots meta"""
        from django.contrib.auth.models import User
        self._seed()
        staff = User.objects.create_user('staff', password='x', is_staff=True)
        client = Client(); client.force_login(staff)
        response = client.get(f'/stories/{self.SLUG}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'sd-draft-banner')
        self.assertContains(response, 'noindex')

    def test_signed_in_non_staff_still_gets_404(self):
        """GIVEN a draft story and a signed-in creator who is not staff
        WHEN they open its URL
        THEN the response is 404"""
        from django.contrib.auth.models import User
        self._seed()
        user = User.objects.create_user('creator', password='x')
        client = Client(); client.force_login(user)
        self.assertEqual(client.get(f'/stories/{self.SLUG}/').status_code, 404)

    def test_admin_publish_action_publishes_and_dates(self):
        """GIVEN a draft story without a date and a superuser
        WHEN the admin "Publish" action runs on it
        THEN it is published with a date and shows on /stories/ without the banner"""
        from django.contrib.auth.models import User
        story = self._seed()
        Story.objects.filter(pk=story.pk).update(published_date=None)
        admin_user = User.objects.create_superuser('boss', 'b@example.org', 'x')
        client = Client(); client.force_login(admin_user)
        response = client.post('/admin/survey/story/', {'action': 'publish_stories', '_selected_action': [story.pk]})
        self.assertEqual(response.status_code, 302)
        story.refresh_from_db()
        self.assertTrue(story.is_published)
        self.assertIsNotNone(story.published_date)
        self.assertContains(Client().get('/stories/'), self.SLUG)
        self.assertNotContains(Client().get(f'/stories/{self.SLUG}/'), 'sd-draft-banner')

    def test_admin_unpublish_action_hides_the_story(self):
        """GIVEN a published story
        WHEN the admin "Unpublish" action runs on it
        THEN visitors get 404 again"""
        from django.contrib.auth.models import User
        story = self._seed('--publish')
        admin_user = User.objects.create_superuser('boss', 'b@example.org', 'x')
        client = Client(); client.force_login(admin_user)
        client.post('/admin/survey/story/', {'action': 'unpublish_stories', '_selected_action': [story.pk]})
        self.assertEqual(Client().get(f'/stories/{self.SLUG}/').status_code, 404)

    def test_from_dir_installs_a_story_kept_outside_the_repo(self):
        """GIVEN a story directory outside survey/story_data/ (a draft not yet approved)
        WHEN seed_story runs with --from that directory
        THEN the story is installed as a draft under the given slug"""
        import shutil, tempfile
        from pathlib import Path
        from survey.management.commands.seed_story import DATA_ROOT
        tmp = Path(tempfile.mkdtemp()) / 'elsewhere'
        shutil.copytree(DATA_ROOT / self.SLUG, tmp)
        from io import StringIO
        from django.core.management import call_command
        call_command('seed_story', 'kept-outside', '--from', str(tmp), stdout=StringIO())
        story = Story.objects.get(slug='kept-outside')
        self.assertFalse(story.is_published)
        self.assertTrue(story.cover_image)


class StoryDisplayOrderTest(TestCase):
    """Change story-display-order: the admin decides which stories come first."""

    def setUp(self):
        from datetime import timedelta
        from django.utils import timezone
        now = timezone.now()
        mk = lambda slug, days, pos=None: Story.objects.create(
            title=slug, slug=slug, story_type="case-study", is_published=True,
            published_date=now - timedelta(days=days), position=pos)
        self.newest = mk('newest', 0)
        self.older = mk('older', 5)
        self.second = mk('second', 3, pos=2)
        self.first = mk('first', 9, pos=1)

    def test_positioned_first_then_newest(self):
        """GIVEN two stories with positions 1 and 2 and two without
        WHEN they are put in showcase order
        THEN position 1, position 2, then the unpositioned ones newest first"""
        order = [s.slug for s in Story.in_showcase_order()]
        self.assertEqual(order, ['first', 'second', 'newest', 'older'])

    def test_stories_index_and_landing_follow_the_order(self):
        """GIVEN the same four stories
        WHEN /stories/ and the landing render
        THEN the cards appear in showcase order"""
        for url in ('/stories/', '/'):
            body = self.client.get(url).content.decode()
            idx = [body.find(f'/stories/{slug}/') for slug in ('first', 'second', 'newest', 'older')]
            self.assertTrue(all(i > 0 for i in idx), url)
            self.assertEqual(idx, sorted(idx), url)

    def test_seed_story_keeps_the_position(self):
        """GIVEN the Olney story installed with position 1 set in the admin
        WHEN seed_story runs again
        THEN the position is still 1"""
        from io import StringIO
        from django.core.management import call_command
        call_command('seed_story', 'olney-white-squirrel-count', stdout=StringIO())
        Story.objects.filter(slug='olney-white-squirrel-count').update(position=1)
        call_command('seed_story', 'olney-white-squirrel-count', stdout=StringIO())
        self.assertEqual(Story.objects.get(slug='olney-white-squirrel-count').position, 1)
